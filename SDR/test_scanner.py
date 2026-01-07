# (Append this at the bottom of scanner.py for a quick self-test)
if __name__ == "__main__":
    # Simple self-test of the scanning logic with synthetic data.
    print("Running SDR Scanner self-test...")
    # Create a dummy SDRIngest by monkey-patching SDRIngest to return synthetic samples
    import numpy as np
    class DummySDR:
        def __init__(self):
            self.sample_rate = 48000  # 48 kHz dummy sample rate
            self.center_freq = 100e6
        def read_samples(self, num_samples):
            # Generate num_samples of complex samples.
            # For test: simulate mostly noise and occasionally a tone indicating a signal.
            t = np.arange(num_samples) / self.sample_rate
            # Create a tone at 1 kHz
            tone = 0.5 * np.exp(1j*2*np.pi*1000*t)  # 0.5 amplitude
            # Create noise
            noise = 0.05 * (np.random.randn(num_samples) + 1j*np.random.randn(num_samples))
            # Combine tone and noise
            samples = tone + noise
            # To simulate silence vs signal, we can gate the tone on/off if needed.
            return samples.astype(np.complex64)
        def tune(self, freq):
            # Dummy tune does nothing
            self.center_freq = freq
        def close(self):
            pass
    
    # Monkey patch the SDRIngest in ScannerThread to use DummySDR
    SDRIngest_backup = SDRIngest
    SDRIngest = lambda **kwargs: DummySDR()  # override for testing
    
    # Monkey patch Transcriber to avoid loading model (for speed)
    from transcriber import Transcriber as RealTranscriber
    class DummyTranscriber:
        def __init__(self, model_size=None):
            pass
        def transcribe_audio(self, audio_data, sample_rate):
            # Instead of real transcription, just return a dummy text
            return "[Dummy Transcription]"
    # Replace Transcriber in our ScannerThread with DummyTranscriber for test
    Transcriber_backup = Transcriber
    Transcriber = DummyTranscriber
    
    # Create scanner thread in test mode (not as QThread, just call run directly for simplicity)
    scanner = ScannerThread(freq_range=(100e6, 100e6, 0), mode='FM', gain=None, squelch=0.1, scan_mode=False)
    scanner.sdr = DummySDR()  # use dummy SDR
    scanner.transcriber = DummyTranscriber()
    # Run a few iterations manually
    for i in range(10):
        samples = scanner.sdr.read_samples(scanner.block_size)
        power_val = compute_power(samples)
        if power_val > scanner.squelch_threshold:
            print(f"Test: Signal detected (power {power_val:.3f})")
            audio = demodulate(samples, scanner.mode, scanner.sdr.sample_rate)
            text = scanner.transcriber.transcribe_audio(audio, sample_rate=scanner.sdr.sample_rate)
            event = scanner.logger.log_event(scanner.sdr.center_freq, text)
            print(f"Logged Event: {event}")
        else:
            print(f"Test: No significant signal (power {power_val:.3f})")
    # Cleanup
    scanner.logger.close()
    # Restore patched classes
    SDRIngest = SDRIngest_backup
    Transcriber = Transcriber_backup
