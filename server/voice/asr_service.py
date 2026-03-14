import logging
from faster_whisper import WhisperModel

logger = logging.getLogger("api.asr")

class ASRService:
    def __init__(self):
        self.model = None

    def load(self):
        if self.model is None:
            logger.info("[ASR] Loading Faster-Whisper model 'tiny.en' on CPU...")
            self.model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logger.info("[ASR] Model loaded successfully.")

    def transcribe_audio(self, audio_path: str) -> str:
        """
        Convert audio file to text using Faster-Whisper.
        """
        self.load()
        logger.info(f"[ASR] Transcribing audio from {audio_path}")
        segments, info = self.model.transcribe(audio_path, beam_size=5)
        
        text_segments = []
        for segment in segments:
            text_segments.append(segment.text)
            
        final_text = "".join(text_segments).strip()
        logger.info(f"[ASR] Transcription result: \"{final_text}\"")
        return final_text

# Create a global instance so it's loaded only once
asr_service_instance = ASRService()
