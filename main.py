import sys
import os
import asyncio
import logging
from pyrogram import Client, idle
from pytgcalls import PyTgCalls

import config
from relay.manager import RelayManager
from commands.controls import register_controls
from control_bot.bot import register_control_bot
from mirror.handler import register_mirror

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_pyrogram_client(session_val: str, default_name: str) -> Client:
    """Helper to instantiate Pyrogram Client handling both Session Strings and Session File Names."""
    session_val = (session_val or "").strip()
    # Pyrogram String Sessions are long Base64 strings (typically > 50 characters)
    if len(session_val) > 50:
        logger.info(f"Using String Session for '{default_name}'")
        return Client(
            name=default_name,
            session_string=session_val,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            in_memory=True
        )
    else:
        session_name = session_val or default_name
        session_path = os.path.join("sessions", session_name)
        logger.info(f"Using Session File '{session_path}'")
        return Client(
            name=session_path,
            api_id=config.API_ID,
            api_hash=config.API_HASH
        )


async def main():
    logger.info("Initializing VC Audio Relay Bot...")

    errors = config.validate()
    if errors:
        for e in errors:
            logger.error(f"❌ Config error: {e}")
        logger.error("Fix the .env file and restart. See .env.example.")
        sys.exit(1)

    os.makedirs("sessions", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # ── Userbot account(s) for VC relay ─────────────────────────────────────
    is_single_account = (config.SESSION_LISTENER == config.SESSION_BROADCASTER) or bool(os.getenv("SESSION_NAME"))

    if is_single_account:
        logger.info("🔑 Operating in SINGLE-ACCOUNT Mode (1 Pyrogram account handling both VC1 and VC2)...")
        app = create_pyrogram_client(config.SESSION_NAME, "single_account")
        listener_app = app
        broadcaster_app = app
        clients_to_start = [app]

        single_call = PyTgCalls(app)
        listener_call = single_call
        broadcaster_call = single_call
        calls_to_start = [single_call]
    else:
        logger.info("🔑 Operating in DUAL-ACCOUNT Mode (2 separate accounts)...")
        listener_app = create_pyrogram_client(config.SESSION_LISTENER, "listener_account")
        broadcaster_app = create_pyrogram_client(config.SESSION_BROADCASTER, "broadcaster_account")
        clients_to_start = [listener_app, broadcaster_app]

        listener_call = PyTgCalls(listener_app)
        broadcaster_call = PyTgCalls(broadcaster_app)
        calls_to_start = [listener_call, broadcaster_call]

    # ── Mirror account (defaults to the listener account — no extra login) ──
    if config.SESSION_MIRROR == config.SESSION_LISTENER:
        mirror_app = listener_app
    else:
        logger.info("🔑 Using a dedicated account for channel mirroring...")
        mirror_app = create_pyrogram_client(config.SESSION_MIRROR, "mirror_account")
        clients_to_start.append(mirror_app)

    # ── Control bot (Bot-API, owner-only buttons) ───────────────────────────
    control_bot = Client(
        name="control_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )

    # ── Wire everything together ─────────────────────────────────────────
    relay_manager = RelayManager(
        listener_client=listener_app,
        listener_call=listener_call,
        broadcaster_client=broadcaster_app,
        broadcaster_call=broadcaster_call
    )

    register_controls(listener_app, relay_manager)      # secondary text-command interface (owner-only)
    register_control_bot(control_bot, relay_manager)    # primary button control panel (owner-only)
    register_mirror(mirror_app)                         # source -> dest channel mirroring

    logger.info("Starting Pyrogram client(s), control bot, and PyTgCalls engine(s)...")

    try:
        for client in clients_to_start:
            await client.start()
        await control_bot.start()

        for call in calls_to_start:
            await call.start()
    except Exception as start_err:
        logger.exception(f"❌ Error during client startup: {start_err}")
        return

    bot_me = await control_bot.get_me()
    logger.info("✅ All clients started successfully!")
    logger.info(f"🤖 Control bot is live: @{bot_me.username} — send /start (owner only).")
    logger.info(f"📡 Mirror: {config.SOURCE_CHANNEL} -> {config.DEST_CHANNEL} (enabled={config.MIRROR_ENABLED})")

    try:
        await idle()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Keyboard interrupt received.")
    finally:
        logger.info("Shutting down clients...")
        try:
            await relay_manager.stop_relay()
        except Exception as e:
            logger.warning(f"Error stopping relay: {e}")

        try:
            await control_bot.stop()
        except Exception as e:
            logger.warning(f"Error stopping control bot: {e}")

        for client in clients_to_start:
            try:
                await client.stop()
            except Exception as e:
                logger.warning(f"Error stopping client: {e}")

        logger.info("Shutdown complete.")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
