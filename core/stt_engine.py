from pathlib import Path
from faster_whisper import WhisperModel
import numpy as np
import threading
import queue
import time

class STTEngine:
    def __init__(self, model_size="small", device="auto", compute_type="int8"):
        # Resolve models relative to the project/executable location, not the
        # process working directory.
        project_root = Path(__file__).resolve().parent.parent
        local_model_path = project_root / "models" / model_size
        
        # Check for CTranslate2 format (model.bin) which faster-whisper requires
        if local_model_path.exists() and (local_model_path / "model.bin").exists():
            print(f"Loading Whisper Model from local path: {local_model_path}")
            model_to_load = local_model_path
        else:
            # Map common model sizes to Hugging Face model IDs
            model_map = {
                "tiny": "Systran/faster-whisper-tiny",
                "base": "Systran/faster-whisper-base",
                "small": "Systran/faster-whisper-small",
                "medium": "Systran/faster-whisper-medium",
                "large-v3": "Systran/faster-whisper-large-v3",
            }
            model_to_load = model_map.get(model_size, model_size)
            print(f"Loading Whisper Model from Hub: {model_to_load} ({device}, {compute_type})...")

        try:
            self.model = WhisperModel(model_to_load, device=device, compute_type=compute_type)
            
            # FIX: faster-whisper bug with large-v3 (128 mel vs 80 mel)
            # Regenerate mel filters to match model's n_mels (official workaround)
            # Must use .astype("float32") to avoid "Unsupported type: <f8" error
            if hasattr(self.model, 'feature_extractor') and hasattr(self.model, 'model'):
                self.model.feature_extractor.mel_filters = self.model.feature_extractor.get_mel_filters(
                    self.model.feature_extractor.sampling_rate,
                    self.model.feature_extractor.n_fft,
                    n_mels=self.model.model.n_mels
                ).astype("float32")
            
            print("Model loaded successfully.")
        except Exception as e:
            print(f"Error loading model (trying CPU fallback): {e}")
            self.model = WhisperModel(model_to_load, device="cpu", compute_type="int8")

        self.input_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.running = False
        self.processing_thread = None

    def start(self):
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.processing_thread.start()

    def stop(self):
        self.running = False
        if self.processing_thread:
            self.processing_thread.join()

    def add_audio(self, audio_data):
        if audio_data is not None and len(audio_data) > 0:
            self.input_queue.put(audio_data)

    def _process_loop(self):
        accumulated_audio = np.array([], dtype=np.float32)
        last_preview_text = ""
        last_nonempty_text = ""
        last_final_text = ""
        same_text_count = 0
        
        while self.running:


            try:
                # 1. Fetch new audio (non-blocking)
                new_chunks = []
                while not self.input_queue.empty():
                    new_chunks.append(self.input_queue.get())
                
                if new_chunks:
                    chunk_data = np.concatenate(new_chunks).astype(np.float32)
                    if len(accumulated_audio) == 0:
                        last_final_text = ""
                    accumulated_audio = np.concatenate((accumulated_audio, chunk_data)).astype(np.float32)
                
                # Limit buffer size (e.g., keep last 8 seconds max)
                if len(accumulated_audio) > 16000 * 8:
                     accumulated_audio = accumulated_audio[-16000*8:]
                
                # If buffer is too short, wait
                if len(accumulated_audio) < 16000 * 0.4: # Minimum 0.4s to start guessing
                    time.sleep(0.05)
                    continue

                current_text = ""

                # --- 2. Real-time Preview (Intermediate) ---
                # Check energy to avoid hallucinating on silence
                energy = np.mean(accumulated_audio**2)
                if energy > 0.00005:
                    try:
                         # Transcribe current buffer (Fast greedy search)
                        segments, info = self.model.transcribe(
                            accumulated_audio,
                            beam_size=3,  # Better Japanese recognition than greedy search
                            language="ja",
                            vad_filter=True,  # Filter silence and reduce hallucinations
                            vad_parameters=dict(min_silence_duration_ms=300),
                            condition_on_previous_text=False
                        )
                        current_text = " ".join([segment.text for segment in segments]).strip()
                        
                        # ANTI-HALLUCINATION FILTER
                        HALLUCINATIONS = ["ご視聴ありがとうございました", "視聴ありがとうございました", "チャンネル登録"]
                        if any(h in current_text for h in HALLUCINATIONS) and len(current_text) < 30:
                            current_text = ""
                            
                        if current_text:
                            last_nonempty_text = current_text
                            # Send partial result (True means "is_partial")
                            print(f"Preview: {current_text}")
                            self.result_queue.put((current_text, True))
                            
                            # Stable text detection
                            if current_text == last_preview_text:
                                same_text_count += 1
                            else:
                                same_text_count = 0
                                last_preview_text = current_text
                                
                    except Exception as e:
                        print(f"Preview error: {e}")

                # --- 3. Finalize Sentence (Logic: Text Stable OR Hard Timeout OR Silence) ---
                
                # Condition A: Text hasn't changed for 3 frames (approx 0.5s) AND it's not empty
                text_stable = (same_text_count >= 3 and len(current_text) > 0)
                
                # Condition B: Hard timeout (> 5s audio)
                timeout = (len(accumulated_audio) > 16000 * 5)
                
                # Condition C: Silence at tail (strict)
                tail_energy = np.mean(accumulated_audio[-int(16000*0.4):]**2) if len(accumulated_audio) > 3000 else 0
                silence_end = (tail_energy < 0.00005 and len(accumulated_audio) > 16000 * 1.5)

                if text_stable or timeout or silence_end:
                    # Sentence ended. Keep the last valid text if the final
                    # transcription pass is empty because VAD trimmed the tail.
                    final_text = current_text or last_nonempty_text
                    if final_text and final_text != last_final_text:
                         print(f"FINAL (Stable={text_stable}, Timeout={timeout}): {final_text}")
                         self.result_queue.put((final_text, False)) # False = Final
                         last_final_text = final_text
                    
                    # Clear buffer
                    accumulated_audio = np.array([], dtype=np.float32)
                    last_preview_text = ""
                    last_nonempty_text = ""
                    same_text_count = 0
                
                # If pure silence for too long, just clear
                if energy < 0.00002 and len(accumulated_audio) > 16000 * 3:
                     accumulated_audio = np.array([], dtype=np.float32)
                     last_preview_text = ""
                     last_nonempty_text = ""
                     same_text_count = 0

                time.sleep(0.15) # Refresh rate ~6fps

            except Exception as e:
                print(f"STT Error: {e}")
                time.sleep(1)

    def get_result(self):
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None
