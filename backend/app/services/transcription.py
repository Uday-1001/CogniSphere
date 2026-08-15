import subprocess
import os
import uuid
from typing import Tuple, Optional
from groq import Groq
from ..config.settings import settings


class TranscriptionService:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self) -> Groq:
        if self._client is None:
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client

    def extract_audio_from_video(self, video_path: str, output_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            subprocess.run([
                "ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
                "-ar", "16000", "-ac", "1", "-b:a", "32k", output_path, "-y"
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def transcribe_audio(self, audio_path: str) -> Tuple[str, list]:
        client = self.get_client()
        with open(audio_path, "rb") as file:
            response = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                prompt="This is an audio file. Please transcribe all speech and lyrics faithfully, including repetitions, without skipping any content."
            )
        
        segments_list = []
        for segment in getattr(response, "segments", []):
            segments_list.append({
                "start": str(segment.get("start") if isinstance(segment, dict) else getattr(segment, "start")),
                "end": str(segment.get("end") if isinstance(segment, dict) else getattr(segment, "end")),
                "text": segment.get("text") if isinstance(segment, dict) else getattr(segment, "text"),
                "language": getattr(response, "language", "en")
            })
            
        return getattr(response, "text", ""), segments_list

    def transcribe_video(self, video_path: str, output_dir: str) -> Tuple[str, Optional[str], list]:
        os.makedirs(output_dir, exist_ok=True)
        audio_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.mp3")
        if not self.extract_audio_from_video(video_path, audio_path):
            return "", None, []
        transcript, segments = self.transcribe_audio(audio_path)
        transcript_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        return transcript, transcript_path, segments

    def transcribe_audio_file(self, audio_path: str, output_dir: str) -> Tuple[str, Optional[str], list]:
        transcript, segments = self.transcribe_audio(audio_path)
        os.makedirs(output_dir, exist_ok=True)
        transcript_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        return transcript, transcript_path, segments


transcription_service = TranscriptionService()