import logging
import asyncio
from pyrogram import Client
from pytgcalls import PyTgCalls
from relay.buffer import JitterBuffer
from relay.listener import VC1Listener
from relay.broadcaster import VC2Broadcaster
import config

logger = logging.getLogger(__name__)


class RelayManager:
    """
    Central Manager orchestrating the Voice Chat Relay system.
    Coordinates Account 1 (Listener), JitterBuffer, and Account 2 (Broadcaster).

    States:
      IDLE     -> not connected to either VC
      JOINED   -> connected to both VCs in standby (silent), via 'VC Join'
      RELAYING -> actively recording VC1 and broadcasting to VC2
    """
    def __init__(self, listener_client: Client, listener_call: PyTgCalls, broadcaster_client: Client, broadcaster_call: PyTgCalls):
        self.listener_client = listener_client
        self.listener_call = listener_call
        self.broadcaster_client = broadcaster_client
        self.broadcaster_call = broadcaster_call

        self.buffer = JitterBuffer(
            target_delay_sec=config.TARGET_DELAY_SEC,
            max_delay_sec=config.MAX_DELAY_SEC,
            frame_duration_sec=config.FRAME_DURATION_SEC
        )

        self.listener = VC1Listener(self.listener_client, self.listener_call, self.buffer)
        self.broadcaster = VC2Broadcaster(self.broadcaster_client, self.broadcaster_call, self.buffer)

        self.is_relaying = False
        self.is_joined = False  # standby (silent) join, without relay
        self.chat_vc1 = config.CHAT_VC1
        self.chat_vc2 = config.CHAT_VC2

    # ── VC Join (standby) ────────────────────────────────────────────────
    async def join_only(self, chat_vc1=None, chat_vc2=None):
        """Join both VC1 & VC2 in standby (no recording/relaying yet)."""
        if self.is_relaying:
            return False, "⚠️ Relay is already running. Use ⏹ VC End first."
        if self.is_joined:
            return False, "⚠️ Already joined & on standby in both VCs."

        self.chat_vc1 = chat_vc1 or self.chat_vc1 or config.CHAT_VC1
        self.chat_vc2 = chat_vc2 or self.chat_vc2 or config.CHAT_VC2

        if not self.chat_vc1 or not self.chat_vc2:
            return False, "❌ Missing VC1 or VC2 Chat IDs! Please check config."

        if self.chat_vc1 == self.chat_vc2:
            return False, "❌ VC1 and VC2 cannot be the same chat (would cause a feedback loop)."

        logger.info(f"Joining standby -> VC1 ({self.chat_vc1}) & VC2 ({self.chat_vc2})")

        try:
            await self.listener.join_silent(self.chat_vc1)
            await self.broadcaster.join_silent(self.chat_vc2)
            self.is_joined = True
            return True, (
                f"🔗 **Joined VCs (Standby)**\n"
                f"🎧 VC1: `{self.chat_vc1}`\n"
                f"📢 VC2: `{self.chat_vc2}`\n\n"
                f"No audio is being relayed yet — press ▶️ VC Start to begin."
            )
        except Exception as e:
            logger.error(f"Failed to join VCs: {e}")
            await self._safe_leave_both()
            return False, f"❌ Failed to join: {str(e)}"

    # ── VC Start (full relay) ────────────────────────────────────────────
    async def start_relay(self, chat_vc1=None, chat_vc2=None):
        """Start recording from VC1 and broadcasting to VC2."""
        if self.is_relaying:
            return False, "⚠️ Relay is already running! Use ⏹ VC End first."

        self.chat_vc1 = chat_vc1 or self.chat_vc1 or config.CHAT_VC1
        self.chat_vc2 = chat_vc2 or self.chat_vc2 or config.CHAT_VC2

        if not self.chat_vc1 or not self.chat_vc2:
            return False, "❌ Missing VC1 or VC2 Chat IDs! Please check config or specify in command."

        if self.chat_vc1 == self.chat_vc2:
            return False, "❌ VC1 and VC2 cannot be the same chat (would cause a feedback loop)."

        logger.info(f"Initiating relay from VC1 ({self.chat_vc1}) -> VC2 ({self.chat_vc2})")

        self.buffer.clear()
        self.is_relaying = True

        try:
            # 1. Start Listener in VC1 (switches over if already silent-joined)
            await self.listener.start(self.chat_vc1)

            # 2. Start Broadcaster in VC2 (switches over if already silent-joined)
            await self.broadcaster.start(self.chat_vc2)

            self.is_joined = True  # relaying implies joined
            return True, (
                f"✅ **Relay Started!**\n"
                f"🎧 Listening: `{self.chat_vc1}`\n"
                f"📢 Broadcasting: `{self.chat_vc2}`\n"
                f"⏱️ Target Cushion: `{self.buffer.target_delay_sec}s`"
            )
        except Exception as e:
            logger.error(f"Failed to start relay: {e}")
            self.is_relaying = False
            await self._safe_leave_both()
            return False, f"❌ Failed to start relay: {str(e)}"

    # ── VC End ────────────────────────────────────────────────────────────
    async def stop_relay(self):
        """Stop listening/broadcasting (or leave standby), flush buffer, leave both VCs."""
        if not self.is_relaying and not self.is_joined:
            return False, "⚠️ Not connected to any VC right now."

        logger.info("Stopping voice chat relay / standby...")
        was_relaying = self.is_relaying
        self.is_relaying = False
        self.is_joined = False

        await self._safe_leave_both()
        self.buffer.clear()

        if was_relaying:
            return True, "🛑 **Relay Stopped cleanly.** Left both VC1 and VC2."
        return True, "🛑 **Left standby.** Disconnected from both VC1 and VC2."

    async def _safe_leave_both(self):
        await asyncio.gather(
            self.listener.stop(),
            self.broadcaster.stop(),
            return_exceptions=True
        )

    def set_target_delay(self, seconds: float):
        """Update buffer target delay cushion."""
        self.buffer.set_target_delay(seconds)
        return f"⏱️ Target delay cushion set to `{seconds}s`."

    def get_status(self) -> str:
        """Return formatted human-readable status overview."""
        stats = self.buffer.get_stats()
        if self.is_relaying:
            status_icon = "🟢 RELAYING"
        elif self.is_joined:
            status_icon = "🟡 JOINED (standby)"
        else:
            status_icon = "🔴 IDLE"

        msg = (
            f"📊 **VC Relay Status**: {status_icon}\n"
            f"──────────────────\n"
            f"🎧 **VC1 (Listener)**: `{self.chat_vc1 or 'Not Set'}`\n"
            f"📢 **VC2 (Broadcaster)**: `{self.chat_vc2 or 'Not Set'}`\n"
            f"⏱️ **Target Cushion**: `{stats['target_delay_seconds']}s`\n"
            f"📦 **Current Buffer**: `{stats['buffered_seconds']}s` ({stats['buffered_chunks']} chunks)\n"
            f"🔄 **State**: `{'Buffering cushion...' if stats['is_buffering'] and self.is_relaying else ('Relaying live' if self.is_relaying else ('Standby' if self.is_joined else 'Idle'))}`\n"
            f"📈 **Total Frames Recv**: `{stats['total_received']}`\n"
            f"📉 **Dropped Overflows**: `{stats['total_dropped']}`\n"
            f"⏰ **Uptime**: `{stats['uptime_seconds']}s`"
        )
        return msg
