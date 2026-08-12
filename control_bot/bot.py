import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import MessageNotModified
from relay.manager import RelayManager
import config

logger = logging.getLogger(__name__)


def _panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ VC Start", callback_data="vc_start"),
            InlineKeyboardButton("⏹ VC End", callback_data="vc_end"),
        ],
        [
            InlineKeyboardButton("🔗 VC Join", callback_data="vc_join"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Status", callback_data="vc_refresh"),
        ],
    ])


def _panel_text(relay_manager: RelayManager) -> str:
    return (
        "🎛 **VC Relay — Control Panel**\n\n"
        f"{relay_manager.get_status()}\n\n"
        "▶️ **VC Start** — join & relay live audio VC1 → VC2\n"
        "⏹ **VC End** — stop relay/standby, leave both VCs\n"
        "🔗 **VC Join** — join both VCs on standby (no audio yet)"
    )


def register_control_bot(bot: Client, relay_manager: RelayManager):
    """
    Register the owner-only button control panel on the Bot-API client.
    Only config.OWNER_ID may issue commands or press buttons.
    """

    def is_owner(user_id: int) -> bool:
        return bool(config.OWNER_ID) and user_id == config.OWNER_ID

    @bot.on_message(filters.command(["start", "panel"]))
    async def start_cmd(c: Client, m: Message):
        if not is_owner(m.from_user.id):
            await m.reply_text("⛔ This bot is private and can only be used by its owner.")
            return
        await m.reply_text(_panel_text(relay_manager), reply_markup=_panel_keyboard())

    @bot.on_callback_query()
    async def on_callback(c: Client, cq: CallbackQuery):
        if not is_owner(cq.from_user.id):
            await cq.answer("⛔ You are not authorized to use this bot.", show_alert=True)
            return

        data = cq.data

        if data == "vc_start":
            await cq.answer("Starting relay…")
            success, response = await relay_manager.start_relay()
            await cq.message.reply_text(response)

        elif data == "vc_end":
            await cq.answer("Stopping…")
            success, response = await relay_manager.stop_relay()
            await cq.message.reply_text(response)

        elif data == "vc_join":
            await cq.answer("Joining VCs (standby)…")
            success, response = await relay_manager.join_only()
            await cq.message.reply_text(response)

        elif data == "vc_refresh":
            await cq.answer("Refreshed")

        else:
            await cq.answer()
            return

        # Refresh the panel message in place with the latest status.
        try:
            await cq.message.edit_text(_panel_text(relay_manager), reply_markup=_panel_keyboard())
        except MessageNotModified:
            pass
        except Exception as e:
            logger.debug(f"Panel refresh note: {e}")

    @bot.on_message(filters.command("setdelay"))
    async def set_delay_cmd(c: Client, m: Message):
        if not is_owner(m.from_user.id):
            return
        if len(m.command) < 2:
            return await m.reply_text("⚠️ Usage: `/setdelay <seconds>` (e.g. `/setdelay 2.5`)")
        try:
            sec = float(m.command[1])
            res = relay_manager.set_target_delay(sec)
            await m.reply_text(res)
        except ValueError:
            await m.reply_text("❌ Invalid delay value! Please specify a number in seconds.")

    @bot.on_message(filters.private & ~filters.command(["start", "panel", "setdelay"]))
    async def catch_all(c: Client, m: Message):
        if not is_owner(m.from_user.id):
            await m.reply_text("⛔ This bot is private and can only be used by its owner.")
            return
        await m.reply_text(_panel_text(relay_manager), reply_markup=_panel_keyboard())

    logger.info("🎛 Control bot registered (owner-only, buttons: VC Start / VC End / VC Join).")
