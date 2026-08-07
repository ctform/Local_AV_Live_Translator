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
        whisper_model = "kotoba-whisper-v2"  # Japanese-optimized model
        trans_model = "hy-mt2-1.8b"  # Tencent HY-MT2 1.8B (fast)
        self.audio_cap = AudioCapture(device_index=25)  # Realtek扬声器Loopback [25]
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

    def _async_translate(self, text, is_preview, lock):
        """Background translation task"""
        try:
            import time
            
            # --- CACHE LOGIC ---
            if not hasattr(self, 'translation_cache'):
                self.translation_cache = {}
                
            cached_cn = self.translation_cache.get(text)
            
            if cached_cn:
                cn_text = cached_cn
                latency_ms = 0 # Instant!
                # print(f"Cache Hit for: {text[:10]}...")
            else:
                t0 = time.time()
                cn_text = self.translator.translate(text)
                latency_ms = (time.time() - t0) * 1000
                
                if cn_text:
                    self.translation_cache[text] = cn_text
                    if len(self.translation_cache) > 1000: self.translation_cache.clear()
            
            tag = "PREVIEW" if is_preview else "FINAL"
            print(f"[{tag}] TRANSLATED ({latency_ms:.0f}ms): {cn_text}")
            
            # FIX: If preview, DO NOT send 'text' (JP) back, because it is old.
            if is_preview:
                # Use Gray color for preview to indicate instability
                styled_cn_text = f"<span style='color: #cccccc;'>{cn_text}</span>"
                self.bridge.update_signal.emit("", styled_cn_text)
            else:
                # Final text is normal (white/default)
                # Ensure we strip potential HTML tags if we want clean text, but here we just send raw
                self.bridge.update_signal.emit(text, cn_text)
            
        finally:
            with lock:
                self.is_translating = False

    def _coordination_loop(self):
        import concurrent.futures
        from threading import Lock
        
        # Executor for async translation
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.is_translating = False
        translating_lock = Lock()
        
        
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
                    # FINAL: translate once, without preview throttling.
                    with translating_lock:
                        self.is_translating = True
                    executor.submit(self._async_translate, jp_text, False, translating_lock)

            time.sleep(0.01) # Keep the coordinator responsive

    def stop(self):
        self.running = False
        self.audio_cap.stop()
        self.stt.stop()

if __name__ == "__main__":
    subtitle_app = SubtitleApp()
    subtitle_app.start()
