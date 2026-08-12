import os
import logging
import asyncio
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioQuality, MediaStream
from relay.buffer import JitterBuffer
from relay.audio_utils import ensure_silence_file
import config

logger = logging.getLogger(__name__)

RAW_AUDIO_PATH = os.path.join("data", "relay_audio.wav")


class VC2Broadcaster:
    """
    Broadcaster client connected to Voice Chat 2 (VC2).
    Streams live recorded audio from RAW_AUDIO_PATH into VC2.
    Can also 'silent join' (standby, no relay) for the VC Join button.
    """
    def __init__(self, client: Client, call_py: PyTgCalls, buffer: JitterBuffer):
        self.client = client
        self.call_py = call_py
        self.buffer = buffer
        self.chat_id = None
        self.is_running = False
        self.is_broadcasting = False

    async def _auto_join(self, chat_id):
        try:
            await self.client.join_chat(chat_id)
            logger.info(f"Broadcaster joined chat: {chat_id}")
        except Exception as j_err:
            logger.debug(f"Broadcaster auto-join check: {j_err}")

    async def join_silent(self, chat_id):
        """
        'VC Join' button behaviour: join VC2 and hold the connection open by
        looping a silent audio stream — no relay yet.
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
            self.is_broadcasting = False
            logger.info(f"🔗 Broadcaster silently joined VC2 ({self.chat_id}) — standby, not relaying.")
        except Exception as e:
            logger.exception(f"❌ Error silent-joining VC2: {e}")
            raise

    async def start(self, chat_id):
        """Join VC2 (if not already connected) and initiate audio broadcast from recorded stream."""
        self.chat_id = chat_id
        self.is_running = True
        logger.info(f"Broadcaster joining VC2 in chat {self.chat_id}...")

        await self._auto_join(self.chat_id)

        # Small delay cushion so listener starts recording first
        await asyncio.sleep(self.buffer.target_delay_sec)

        try:
            # Join voice call and play recorded audio stream file using PyTgCalls 2.x play method.
            # If already connected (e.g. via join_silent), this switches the
            # active stream over to the live relay file.
            await self.call_py.play(
                self.chat_id,
                MediaStream(
                    RAW_AUDIO_PATH,
                    audio_parameters=AudioQuality.HIGH,
                    ffmpeg_parameters="-follow 1"
                )
            )
            # Explicitly unmute in VC2 so broadcast audio plays out loud
            try:
                await self.call_py.unmute(self.chat_id)
            except Exception as u_err:
                logger.warning(f"Unmute note: {u_err}")

            self.is_broadcasting = True
            logger.info(f"Broadcaster successfully joined & streaming to VC2 in chat {self.chat_id}")
        except Exception as e:
            logger.exception(f"Error joining VC2: {e}")
            self.is_running = False
            raise e

    async def stop(self):
        """Leave VC2 and release broadcaster resources."""
        self.is_running = False
        self.is_broadcasting = False
        if self.chat_id and self.call_py:
            try:
                await self.call_py.leave_call(self.chat_id)
                logger.info(f"Broadcaster left VC2 in chat {self.chat_id}")
            except Exception as e:
                logger.warning(f"Error leaving VC2: {e}")
        self.chat_id = None
