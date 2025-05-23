# app/processors/audio_processor.py
import queue, threading, asyncio, logging
from google.cloud import speech_v1p1beta1 as speech

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, source_name: str, min_speaker_count=1, max_speaker_count=2):
        self.source_name = source_name
        self.audio_queue = queue.Queue()
        self.response_queue = asyncio.Queue()
        self.thread = None
        self.loop = None
        self.running = False
        self.min_speaker_count = min_speaker_count
        self.max_speaker_count = max_speaker_count

    def start(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.running = True
        self.thread = threading.Thread(target=self._google_streaming, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.audio_queue.put(None)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def add_audio(self, audio_data: bytes):
        if self.running:
            self.audio_queue.put(audio_data)

    def _google_streaming(self):
        diarization_config = speech.SpeakerDiarizationConfig(
            enable_speaker_diarization=True,
            min_speaker_count=self.min_speaker_count,
            max_speaker_count=self.max_speaker_count,
        )
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            diarization_config=diarization_config,
            model="video",
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False,
        )

        def requests():
            while True:
                chunk = self.audio_queue.get()
                if chunk is None:
                    break
                logger.debug(f"{self.source_name}: got {len(chunk)} bytes")
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        try:
            for resp in speech.SpeechClient().streaming_recognize(streaming_config, requests()):
                self.loop.call_soon_threadsafe(self.response_queue.put_nowait, resp)
        except Exception as e:
            logger.error(f"{self.source_name} streaming error: {e}")
