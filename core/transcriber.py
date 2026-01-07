import numpy as np
try:
    import whisper
except ImportError:
    whisper = None

class Transcriber:
    """
    Uses OpenAI Whisper model to transcribe audio to text.
    """
    def __init__(self, model_size="base.en"):
        if whisper is None:
            raise ImportError("Whisper library is not installed.")
        # Load the Whisper model (this can be time-consuming for large models)
        self.model = whisper.load_model(model_size)
    
    def transcribe_audio(self, audio_data, sample_rate):
        """
        Transcribe the given audio data (numpy array) to text.
        audio_data: numpy array of float32 audio samples.
        sample_rate: sample rate of audio_data.
        Returns the transcribed text (string).
        """
        if whisper is None:
            return ""
        # Whisper expects 16 kHz audio. If sample_rate is not 16000, resample or pad/trim:
        target_sr = 16000
        audio = audio_data.astype(np.float32)
        if sample_rate != target_sr:
            # Resample audio to 16000 Hz
            # (In practice, use a proper resampling method. Here we do a simple naive resample for demonstration.)
            import math
            resample_factor = target_sr / float(sample_rate)
            new_length = int(math.ceil(len(audio) * resample_factor))
            # Use numpy interpolation for resampling (simple approach)
            audio = np.interp(np.linspace(0, len(audio), new_length, endpoint=False),
                              np.arange(len(audio)), audio)
        # The whisper library expects the audio to be a numpy array of floats in range [-1,1]
        # Ensure audio is normalized
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        # Use the whisper model to transcribe
        result = self.model.transcribe(audio, fp16=False)
        text = result.get("text", "").strip()
        return text
