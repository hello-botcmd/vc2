import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import config
from mirror import db

logger = logging.getLogger(__name__)


def register_mirror(client: Client):
    """
    Mirrors every post from config.SOURCE_CHANNEL into config.DEST_CHANNEL —
    text, photo, video, document, sticker, animation, voice, video note,
    audio, poll, and anything else Pyrogram's Message.copy() supports.
    Also mirrors edits and deletions when enabled.

    Requires the client's account to be a member/admin of SOURCE_CHANNEL
    (to receive updates) and able to post in DEST_CHANNEL.
    """
    if not config.MIRROR_ENABLED:
        logger.info("📡 Channel mirror disabled (MIRROR_ENABLED=false).")
        return
    if not config.SOURCE_CHANNEL or not config.DEST_CHANNEL:
        logger.warning("📡 Channel mirror skipped: SOURCE_CHANNEL/DEST_CHANNEL not set.")
        return

    db.init_db()

    @client.on_message(filters.chat(config.SOURCE_CHANNEL))
    async def mirror_new_post(c: Client, m: Message):
        """Copy any new post (text/photo/video/sticker/media/poll/...) as-is."""
        try:
            copied = await m.copy(config.DEST_CHANNEL)
        except FloodWait as fw:
            logger.warning(f"📡 FloodWait {fw.value}s while mirroring, retrying...")
            await asyncio.sleep(fw.value)
            try:
                copied = await m.copy(config.DEST_CHANNEL)
            except Exception as e:
                logger.exception(f"❌ Retry failed for message {m.id}: {e}")
                return
        except Exception as e:
            logger.exception(f"❌ Failed to mirror message {m.id}: {e}")
            return

        await asyncio.to_thread(
            db.save_mapping, m.id, copied.id, config.SOURCE_CHANNEL, config.DEST_CHANNEL
        )
        logger.info(f"📤 Mirrored message {m.id} -> {copied.id}")

    if config.MIRROR_EDITS:
        @client.on_edited_message(filters.chat(config.SOURCE_CHANNEL))
        async def mirror_edit(c: Client, m: Message):
            """Propagate text/caption edits to the mirrored copy."""
            dest_id = await asyncio.to_thread(db.get_dest_msg_id, m.id)
            if not dest_id:
                return
            try:
                if m.text is not None:
                    await c.edit_message_text(config.DEST_CHANNEL, dest_id, m.text)
                elif m.caption is not None:
                    await c.edit_message_caption(config.DEST_CHANNEL, dest_id, m.caption)
                logger.info(f"✏️ Mirrored edit for message {m.id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not mirror edit for {m.id}: {e}")

    if config.MIRROR_DELETES:
        @client.on_deleted_messages(filters.chat(config.SOURCE_CHANNEL))
        async def mirror_delete(c: Client, messages):
            """Delete the mirrored copy when the source post is deleted."""
            for m in messages:
                dest_id = await asyncio.to_thread(db.get_dest_msg_id, m.id)
                if not dest_id:
                    continue
                try:
                    await c.delete_messages(config.DEST_CHANNEL, dest_id)
                    logger.info(f"🗑️ Mirrored deletion for message {m.id}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not delete mirrored message: {e}")
                await asyncio.to_thread(db.delete_mapping, m.id)

    logger.info(
        f"📡 Channel mirror active: {config.SOURCE_CHANNEL} → {config.DEST_CHANNEL} "
        f"(edits={config.MIRROR_EDITS}, deletes={config.MIRROR_DELETES})"
    )
