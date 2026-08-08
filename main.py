import os
import sys
import threading
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, qInstallMessageHandler

# Suppress Qt warnings about UpdateLayeredWindowIndirect
def message_handler(mode, context, message):
    if "UpdateLayeredWindowIndirect failed" in message:
        return
    sys.__stderr__.write(message + "\n")
    
qInstallMessageHandler(message_handler)

from core.audio_capture import AudioCapture
from core.stt_engine import STTEngine
from core.translator import TranslatorEngine
from ui.overlay import SubtitleOverlay

class Bridge(QObject):
    """Bridge to send signals from non-GUI threads to GUI"""
    update_signal = pyqtSignal(str, str)

class SubtitleApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.overlay = SubtitleOverlay()
        self.bridge = Bridge()
        self.bridge.update_signal.connect(self.overlay.update_subtitles)

        # Initialize Cores
        print("Initializing engines...")
        
        # Read saved model settings from Overlay's QSettings
        # Note: We access the same QSettings path ("LiveSubtitle", "Overlay")
        from PyQt6.QtCore import QSettings
        settings = QSettings("LiveSubtitle", "Overlay")
        whisper_model = os.environ.get(
            "LAVT_WHISPER_MODEL",
            settings.value("whisper_model", "kotoba-whisper-v2.2-faster")
        )
        trans_model = os.environ.get(
            "LAVT_TRANSLATOR_MODEL",
            settings.value("trans_model", "translategemma:4b")
        )
        device_index = os.environ.get("LAVT_AUDIO_DEVICE_INDEX")
        try:
            device_index = int(device_index) if device_index else None
        except ValueError:
            print(f"Invalid LAVT_AUDIO_DEVICE_INDEX: {device_index}; using auto-detection")
            device_index = None
        self.audio_cap = AudioCapture(device_index=device_index)
        # Load translation model FIRST, then Whisper (avoid loading order issue)
        self.translator = TranslatorEngine(use_ollama=False, model=trans_model)
        self.stt = STTEngine(model_size=whisper_model, device="cuda", compute_type="float16")
        
        self.running = False
        self.coordinator_thread = None

    def start(self):
        self.running = True
        
        # Start Sub-systems
        self.stt.start()
        self.audio_cap.start()
        
        # Start Coordinator (Moves data between systems)
        self.coordinator_thread = threading.Thread(target=self._coordination_loop, daemon=True)
        self.coordinator_thread.start()
        
        # Show UI
        self.overlay.show()
        print("Application started.")
        sys.exit(self.app.exec())

    def _async_translate_batch(self, batch, lock):
        """Translate an ordered batch without blocking the coordinator."""
        try:
            import time

            if not hasattr(self, "translation_cache"):
                self.translation_cache = {}

            missing = []
            results = {}
            for sentence_id, text in batch:
                cached = self.translation_cache.get(text)
                if cached:
                    results[sentence_id] = cached
                else:
                    missing.append((sentence_id, text))

            if missing:
                started = time.time()
                try:
                    translated = self.translator.translate_batch([text for _, text in missing])
                except Exception as exc:
                    print(f"[FINAL] Batch translation error: {exc}")
                    translated = [""] * len(missing)
                print(f"[FINAL] BATCH TRANSLATED ({(time.time() - started) * 1000:.0f}ms): {len(missing)} sentences")
                for (sentence_id, text), cn_text in zip(missing, translated):
                    if cn_text:
                        self.translation_cache[text] = cn_text
                        results[sentence_id] = cn_text
                if len(self.translation_cache) > 1000:
                    self.translation_cache.clear()

            # The executor is single-threaded and batches are submitted in order.
            # Do not write the old Japanese text back over a newer partial subtitle.
            for sentence_id, text in batch:
                cn_text = results.get(sentence_id)
                if cn_text:
                    self.bridge.update_signal.emit("", cn_text)
                else:
                    print(f"[FINAL] Translation failed for sentence {sentence_id}: {text}")
        finally:
            with lock:
                self.is_translating = False

    def _coordination_loop(self):
        import concurrent.futures
        from threading import Lock
        
        # Executor for async translation
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.translation_executor = executor
        self.is_translating = False
        translating_lock = Lock()
        pending_finals = []
        max_pending_finals = 32
        last_final_text = ""
        next_sentence_id = 1
        batch_started_at = None
        BATCH_WINDOW = 0.12
        
        print("Coordinator loop started.")
        while self.running:
            # 1. Get Audio -> Feed to STT
            audio_data = self.audio_cap.get_audio_data()
            if audio_data is not None:
                self.stt.add_audio(audio_data)

            # 2. Get STT Result
            result = self.stt.get_result()
            
            if result:
                jp_text, is_partial = result
                
                if is_partial:
                    # Partial ASR is for live Japanese display only.  Wait for a
                    # final result before sending anything to the translator.
                    self.bridge.update_signal.emit(jp_text, "PENDING_KEEP_OLD")
                else:
                    # FINAL: queue every sentence, then combine nearby short
                    # sentences into one Ollama request.
                    if jp_text and jp_text != last_final_text:
                        if len(pending_finals) >= max_pending_finals:
                            # Preserve order while preventing unbounded latency.
                            pending_finals = pending_finals[-(max_pending_finals - 1):]
                        pending_finals.append((next_sentence_id, jp_text))
                        next_sentence_id += 1
                        last_final_text = jp_text
                        if batch_started_at is None:
                            batch_started_at = time.time()

            if pending_finals and (time.time() - batch_started_at >= BATCH_WINDOW):
                with translating_lock:
                    if not self.is_translating:
                        batch = pending_finals
                        pending_finals = []
                        batch_started_at = None
                        self.is_translating = True
                        executor.submit(self._async_translate_batch, batch, translating_lock)

            time.sleep(0.01) # Keep the coordinator responsive

    def stop(self):
        self.running = False
        self.audio_cap.stop()
        self.stt.stop()
        executor = getattr(self, "translation_executor", None)
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)

if __name__ == "__main__":
    subtitle_app = SubtitleApp()
    subtitle_app.start()
