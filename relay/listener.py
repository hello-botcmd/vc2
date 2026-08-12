import os
import wave
import logging
import asyncio
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality, RecordStream, MediaStream
from relay.buffer import JitterBuffer
from relay.audio_utils import ensure_silence_file

logger = logging.getLogger(__name__)

os.makedirs("data", exist_ok=True)
RAW_AUDIO_PATH = os.path.join("data", "relay_audio.wav")


def create_initial_wav_file():
    """Create a valid 48kHz 16-bit stereo WAV file with initial silence cushion."""
    try:
        with wave.open(RAW_AUDIO_PATH, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b'\x00' * 3840 * 10)  # 200ms initial silence
        logger.info(f"Initialized audio recording file: {RAW_AUDIO_PATH}")
    except Exception as e:
        logger.warning(f"Note creating WAV file: {e}")


class VC1Listener:
    """
    Listener client connected to Voice Chat 1 (VC1).
    Records live audio from VC1 into data/relay_audio.wav with deep diagnostic logging.
    Can also 'silent join' (standby, no recording) for the VC Join button.
    """
    def __init__(self, client: Client, call_py: PyTgCalls, buffer: JitterBuffer):
        self.client = client
        self.call_py = call_py
        self.buffer = buffer
        self.chat_id = None
        self.is_running = False
        self.is_recording = False
        self._monitor_task = None

    async def _monitor_recording(self):
        """Background task logging recording file growth and health every 3 seconds."""
        last_size = 0
        while self.is_running:
            await asyncio.sleep(3.0)
            if os.path.exists(RAW_AUDIO_PATH):
                current_size = os.path.getsize(RAW_AUDIO_PATH)
                growth = current_size - last_size
                size_kb = current_size / 1024.0
                if growth > 0:
                    logger.info(f"🎙️ [RECORDING ACTIVE] File Size: {size_kb:.1f} KB (+{growth} bytes in last 3s)")
                else:
                    logger.info(f"🎙️ [RECORDING IDLE] File Size: {size_kb:.1f} KB (No new audio bytes written in last 3s)")
                last_size = current_size

    async def _auto_join(self, chat_id):
        try:
            await self.client.join_chat(chat_id)
            logger.info(f"Listener joined group: {chat_id}")
        except Exception as j_err:
            logger.debug(f"Listener auto-join check: {j_err}")

    async def join_silent(self, chat_id):
        """
        'VC Join' button behaviour: join VC1 and hold the connection open by
        looping a silent audio stream — no recording, no relay yet.
        """
        self.chat_id = chat_id
        await self._auto_join(chat_id)
        silence_path = ensure_silence_file()

        try:
            await self.call_py.play(
                self.chat_id,
                MediaStream(
                    silence_path,
                    audio_parameters=AudioQuality.HIGH,
                    ffmpeg_parameters="-stream_loop -1"
                )
            )
            self.is_running = True
            self.is_recording = False
            logger.info(f"🔗 Listener silently joined VC1 ({self.chat_id}) — standby, not recording.")
        except Exception as e:
            logger.exception(f"❌ Error silent-joining VC1: {e}")
            raise

    async def start(self, chat_id):
        """Join VC1 (if not already connected) and begin recording audio stream."""
        self.chat_id = chat_id
        self.is_running = True
        logger.info(f"Listener joining VC1 in chat {self.chat_id}...")

        await self._auto_join(self.chat_id)

        # Reset WAV stream file
        create_initial_wav_file()

        # Hook PyTgCalls deep update logger (only once)
        if not getattr(self, "_update_hooked", False):
            @self.call_py.on_update()
            async def on_update_handler(client, update):
                logger.info(f"📡 [PyTgCalls Event] Type: {type(update).__name__} | Details: {update}")
            self._update_hooked = True

        try:
            # Join and record voice call using PyTgCalls 2.x record method.
            # If already connected (e.g. via join_silent), this switches the
            # active stream over to recording mode.
            await self.call_py.record(
                self.chat_id,
                RecordStream(
                    audio=RAW_AUDIO_PATH,
                    audio_parameters=AudioQuality.HIGH
                )
            )
            self.is_recording = True
            logger.info(f"✅ Listener successfully joined & recording VC1 ({self.chat_id}) -> '{RAW_AUDIO_PATH}'")

            # Start recording monitor task
            self._monitor_task = asyncio.create_task(self._monitor_recording())
        except Exception as e:
            logger.exception(f"❌ Error recording VC1: {e}")
            self.is_running = False
            raise e

    async def stop(self):
        """Leave VC1 and release listener resources."""
        self.is_running = False
        self.is_recording = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        if self.chat_id and self.call_py:
            try:
                await self.call_py.leave_call(self.chat_id)
                logger.info(f"Listener left VC1 in chat {self.chat_id}")
            except Exception as e:
                logger.warning(f"Error leaving VC1: {e}")
        self.chat_id = None
