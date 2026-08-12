import os
from dotenv import load_dotenv

load_dotenv()


def _int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _bool(val, default=False):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


# ── Telegram API credentials (MTProto userbot) ──────────────────────────────
API_ID = _int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH", "")

# ── Control Bot (Bot API — the button interface) ────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Only this Telegram user id may use the control bot / press its buttons.
OWNER_ID = _int(os.getenv("OWNER_ID"))

# ── Userbot Sessions ─────────────────────────────────────────────────────────
# If SESSION_NAME is set, ONE account handles VC1, VC2 and mirroring.
SESSION_NAME = os.getenv("SESSION_NAME", os.getenv("SESSION_LISTENER", "relay_session"))
SESSION_LISTENER = os.getenv("SESSION_LISTENER", SESSION_NAME)
SESSION_BROADCASTER = os.getenv("SESSION_BROADCASTER", SESSION_NAME)
# Account used for channel mirroring. Defaults to the listener account so no
# extra login is required unless you explicitly want a 3rd dedicated account.
SESSION_MIRROR = os.getenv("SESSION_MIRROR", SESSION_LISTENER)


def parse_chat_id(val: str):
    """Accepts an int id, a @username, or a t.me/... link."""
    if not val:
        return None
    val = val.strip()
    if "t.me/" in val:
        val = val.split("t.me/")[-1].strip("/").replace("@", "")
    if val.startswith("-") or val.isdigit():
        try:
            return int(val)
        except ValueError:
            pass
    return val


# ── Voice Chat Targets ──────────────────────────────────────────────────────
CHAT_VC1 = parse_chat_id(os.getenv("CHAT_VC1", ""))
CHAT_VC2 = parse_chat_id(os.getenv("CHAT_VC2", ""))

TARGET_DELAY_SEC = float(os.getenv("TARGET_DELAY_SEC", "2.0"))
MAX_DELAY_SEC = float(os.getenv("MAX_DELAY_SEC", "5.0"))

# ── Channel Mirror (post/media/sticker copy: source channel -> dest channel) ─
SOURCE_CHANNEL = parse_chat_id(os.getenv("SOURCE_CHANNEL", ""))
DEST_CHANNEL = parse_chat_id(os.getenv("DEST_CHANNEL", ""))
MIRROR_ENABLED = _bool(os.getenv("MIRROR_ENABLED"), default=True)
MIRROR_EDITS = _bool(os.getenv("MIRROR_EDITS"), default=True)
MIRROR_DELETES = _bool(os.getenv("MIRROR_DELETES"), default=True)

# ── Audio settings (standard PCM 16-bit stereo 48kHz) ───────────────────────
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2
FRAME_DURATION_SEC = 0.02
FRAME_SIZE_BYTES = int(SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * FRAME_DURATION_SEC)


def validate() -> list:
    """Returns a list of human-readable problems; empty list means OK."""
    errors = []
    if not API_ID or not API_HASH:
        errors.append("API_ID / API_HASH missing (userbot credentials)")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN missing (control bot token from @BotFather)")
    if not OWNER_ID:
        errors.append("OWNER_ID missing (your numeric Telegram user id)")
    if not CHAT_VC1 or not CHAT_VC2:
        errors.append("CHAT_VC1 / CHAT_VC2 missing (voice chat targets)")
    if MIRROR_ENABLED and (not SOURCE_CHANNEL or not DEST_CHANNEL):
        errors.append("MIRROR_ENABLED is true but SOURCE_CHANNEL/DEST_CHANNEL missing")
    return errors
