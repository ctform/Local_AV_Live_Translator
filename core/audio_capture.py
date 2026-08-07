"""
Audio capture using PyAudioWPatch for Windows WASAPI Loopback.
This provides better compatibility for capturing system audio on Windows.
"""
import pyaudiowpatch as pyaudio
import numpy as np
import threading
import queue
import time

class AudioCapture:
    def __init__(self, sample_rate=16000, device_index=None):
        """
        :param sample_rate: Audio sample rate (Whisper expects 16000)
        :param device_index: Index of the device to use (None = auto-detect loopback)
        """
        self.sample_rate = sample_rate
        self.audio_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.device_index = device_index
        self.selected_device = None
        self.p = pyaudio.PyAudio()
        
    def __del__(self):
        self.p.terminate()
        
    @staticmethod
    def list_devices():
        """List all available audio devices with loopback support."""
        p = pyaudio.PyAudio()
        print("\n===== 可用音频设备 (Available Audio Devices) =====")
        
        devices = []
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            # Show output devices (which can be used for loopback)
            if dev['maxInputChannels'] > 0 or dev.get('isLoopbackDevice', False):
                is_loopback = dev.get('isLoopbackDevice', False)
                marker = " [LOOPBACK]" if is_loopback else ""
                print(f"  [{i}] {dev['name']}{marker}")
                devices.append(dev)
        
        print("=" * 50)
        print("提示: 带 [LOOPBACK] 标记的设备可以录制系统声音")
        p.terminate()
        return devices
    
    def find_loopback_device(self):
        """Auto-find a suitable loopback device."""
        # Get default output device and find its loopback
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            # Find loopback device for this speaker
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('isLoopbackDevice', False):
                    # Check if this loopback corresponds to our default speakers
                    if default_speakers['name'] in dev['name']:
                        return dev
            
            # If no exact match, just find any loopback device
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('isLoopbackDevice', False):
                    return dev
                    
        except Exception as e:
            print(f"Auto-detect failed: {e}")
        
        return None
    
    def select_device(self):
        """Select or auto-detect a device."""
        if self.device_index is not None:
            # Use pre-configured index
            try:
                self.selected_device = self.p.get_device_info_by_index(self.device_index)
                print(f"使用设备 [{self.device_index}]: {self.selected_device['name']}")
                return True
            except:
                print(f"错误: 设备索引 {self.device_index} 无效")
                return False
        
        # Try auto-detect first
        self.selected_device = self.find_loopback_device()
        if self.selected_device:
            print(f"自动检测到 Loopback 设备: {self.selected_device['name']}")
            return True
        
        # Interactive selection if auto-detect fails
        self.list_devices()
        while True:
            try:
                choice = input("请输入设备编号 (Enter device number): ").strip()
                idx = int(choice)
                self.selected_device = self.p.get_device_info_by_index(idx)
                print(f"已选择: {self.selected_device['name']}")
                return True
            except ValueError:
                print("请输入数字")
            except Exception as e:
                print(f"错误: {e}")
            except KeyboardInterrupt:
                return False
        
    def start(self):
        if not self.selected_device:
            if not self.select_device():
                print("未选择设备，无法启动")
                return False
                
        self.running = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        print("Audio capture started.")
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("Audio capture stopped.")

    def _record_loop(self):
        # List of devices to try: [selected_one, ...others_if_loopback]
        devices_to_try = [self.selected_device] if self.selected_device else []
        
        # If we are in loopback mode, add other loopback devices as fallback
        if self.selected_device and self.selected_device.get('isLoopbackDevice', False):
            # Find all other loopback devices
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('isLoopbackDevice', False) and dev['index'] != self.selected_device['index']:
                    devices_to_try.append(dev)
                    
        for dev_info in devices_to_try:
            print(f"Attempting to record from: {dev_info['name']}")
            
            # Audio stream parameters
            dev_sample_rate = int(dev_info['defaultSampleRate'])
            channels = dev_info['maxInputChannels']
            if channels == 0:
                channels = 2  # Assume stereo for loopback
            
            chunk_size = int(dev_sample_rate * 0.5)  # 0.5 second chunks
            
            try:
                stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=channels,
                    rate=dev_sample_rate,
                    input=True,
                    input_device_index=dev_info['index'],
                    frames_per_buffer=chunk_size
                )
                
                print(f"Successfully started recording from: {dev_info['name']}")
                self.selected_device = dev_info # Update selected if fell back
                
                while self.running:
                    try:
                        # Read audio data
                        data = stream.read(chunk_size, exception_on_overflow=False)
                        audio_data = np.frombuffer(data, dtype=np.float32)
                        
                        # Convert to mono if stereo
                        if channels > 1:
                            audio_data = audio_data.reshape(-1, channels)
                            audio_data = np.mean(audio_data, axis=1)
                        
                        # Resample if needed (simple decimation for now)
                        if dev_sample_rate != self.sample_rate:
                            ratio = dev_sample_rate / self.sample_rate
                            indices = np.arange(0, len(audio_data), ratio).astype(int)
                            audio_data = audio_data[indices]
                        
                        self.audio_queue.put(audio_data.astype(np.float32))
                        
                    except Exception as e:
                        print(f"Recording error: {e}")
                        time.sleep(0.5)
                        
                stream.stop_stream()
                stream.close()
                return # Exit if we successfully recorded and then stopped
                
            except Exception as e:
                print(f"Failed to open device {dev_info['name']}: {e}")
                # Continue to next device in list
        
        print("Error: Could not open any audio device.")
        print("提示: 请尝试选择其他设备，或检查设备是否被其他程序占用")

    def get_audio_data(self):
        """Retrieve all available audio data from queue flattened."""
        data_list = []
        while not self.audio_queue.empty():
            data_list.append(self.audio_queue.get())
        
        if not data_list:
            return None
            
        return np.concatenate(data_list)


# Allow running standalone for device testing
if __name__ == "__main__":
    print("音频设备测试模式 (Audio Device Test Mode)")
    cap = AudioCapture()
    cap.list_devices()
    if cap.select_device():
        cap.start()
        print("录音中... 按 Ctrl+C 停止")
        try:
            while True:
                data = cap.get_audio_data()
                if data is not None:
                    energy = np.mean(data**2)
                    bars = int(energy * 50000)
                    print(f"Audio level: {'|' * min(bars, 50)}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            cap.stop()
