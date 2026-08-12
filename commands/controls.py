import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from relay.manager import RelayManager
import config

logger = logging.getLogger(__name__)


def register_controls(client: Client, relay_manager: RelayManager):
    """
    Register text-command handlers on the USERBOT account, as a secondary
    control surface alongside the button-based control bot.
    Restricted to config.OWNER_ID only.
    """
    owner_only = filters.user(config.OWNER_ID) if config.OWNER_ID else filters.me

    @client.on_message(filters.command("startrelay") & owner_only)
    async def start_relay_cmd(c: Client, m: Message):
        """Handler for /startrelay [chat_vc1] [chat_vc2]"""
        args = m.command[1:]
        chat1 = args[0] if len(args) > 0 else None
        chat2 = args[1] if len(args) > 1 else None

        msg = await m.reply_text("🔄 **Starting VC Relay...**")
        success, response = await relay_manager.start_relay(chat1, chat2)
        await msg.edit_text(response)

    @client.on_message(filters.command("joinvc") & owner_only)
    async def join_vc_cmd(c: Client, m: Message):
        """Handler for /joinvc [chat_vc1] [chat_vc2] — standby join, no relay."""
        args = m.command[1:]
        chat1 = args[0] if len(args) > 0 else None
        chat2 = args[1] if len(args) > 1 else None

        msg = await m.reply_text("🔄 **Joining VCs (standby)...**")
        success, response = await relay_manager.join_only(chat1, chat2)
        await msg.edit_text(response)

    @client.on_message(filters.command("stoprelay") & owner_only)
    async def stop_relay_cmd(c: Client, m: Message):
        """Handler for /stoprelay"""
        msg = await m.reply_text("🛑 **Stopping VC Relay...**")
        success, response = await relay_manager.stop_relay()
        await msg.edit_text(response)

    @client.on_message(filters.command("status") & owner_only)
    async def status_cmd(c: Client, m: Message):
        """Handler for /status"""
        status_text = relay_manager.get_status()
        await m.reply_text(status_text)

    @client.on_message(filters.command("recstats") & owner_only)
    async def recstats_cmd(c: Client, m: Message):
        """Handler for /recstats diagnostic tool."""
        rec_path = os.path.join("data", "relay_audio.wav")
        if os.path.exists(rec_path):
            size_bytes = os.path.getsize(rec_path)
            size_kb = size_bytes / 1024.0
            msg = (
                f"🎙️ **Recording Diagnostic Stats**:\n"
                f"──────────────────\n"
                f"📁 **File**: `{rec_path}`\n"
                f"📦 **Current Size**: `{size_kb:.1f} KB` ({size_bytes} bytes)\n"
                f"⚡ **Status**: `{'Recording Active' if size_bytes > 5000 else 'File Initialized (Speak in VC1 to test growth)'}`"
            )
        else:
            msg = "⚠️ Recording file `data/relay_audio.wav` does not exist yet. Run `/startrelay` first."
        await m.reply_text(msg)

    @client.on_message(filters.command("setdelay") & owner_only)
    async def set_delay_cmd(c: Client, m: Message):
        """Handler for /setdelay <seconds>"""
        if len(m.command) < 2:
            return await m.reply_text("⚠️ Usage: `/setdelay <seconds>` (e.g. `/setdelay 2.5`)")

        try:
            sec = float(m.command[1])
            res = relay_manager.set_target_delay(sec)
            await m.reply_text(res)
        except ValueError:
            await m.reply_text("❌ Invalid delay value! Please specify a number in seconds.")

    logger.info("Userbot control command handlers registered (owner-only).")
