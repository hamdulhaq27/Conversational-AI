import logging
import os
import tempfile
import wave
import base64
import urllib.request
from piper import PiperVoice

logger = logging.getLogger("api.tts")

MODEL_ONNX_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
MODEL_JSON_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

class TTSService:
    def __init__(self):
        self.model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(self.model_dir, exist_ok=True)
        self.model_path = os.path.join(self.model_dir, "en_US-lessac-medium.onnx")
        self.json_path = os.path.join(self.model_dir, "en_US-lessac-medium.onnx.json")
        self.voice = None

    def load(self):
        if self.voice is None:
            self._ensure_model_downloaded()
            logger.info("[TTS] Loading Piper model 'en_US-lessac-medium' on CPU...")
            self.voice = PiperVoice.load(self.model_path)
            logger.info("[TTS] Model loaded successfully.")

    def _ensure_model_downloaded(self):
        if not os.path.exists(self.model_path):
            logger.info("[TTS] Downloading Piper voice model (.onnx)...")
            urllib.request.urlretrieve(MODEL_ONNX_URL, self.model_path)
        if not os.path.exists(self.json_path):
            logger.info("[TTS] Downloading Piper voice config (.json)...")
            urllib.request.urlretrieve(MODEL_JSON_URL, self.json_path)

    def generate_speech(self, text: str) -> str:
        """
        Convert text to speech audio via Piper TTS, and return base64 encoded audio.
        """
        self.load()
        if not text or not text.strip():
            return ""
            
        logger.info(f"[TTS] Generating speech for text: {text}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_path = temp_audio.name
            
        # Piper provides a method to synthesize direct to WAV file.
        with wave.open(temp_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.voice.config.sample_rate)
            self.voice.synthesize_wav(text, wav_file)
            
        # Read WAV to base64
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
            
        os.remove(temp_path)
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"[TTS] Generated audio: {len(audio_base64)} bytes of base64")
        return audio_base64

# Global instance to load only once
tts_service_instance = TTSService()
