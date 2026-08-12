import os
import wave

DATA_DIR = "data"
SILENCE_PATH = os.path.join(DATA_DIR, "silence.wav")


def ensure_silence_file(duration_sec: float = 5.0, sample_rate: int = 48000,
                         channels: int = 2, sample_width: int = 2) -> str:
    """
    Create (once) a short silent WAV file.

    Used by the 'VC Join' button: the userbot joins the voice chat and loops
    this silent file (ffmpeg -stream_loop -1) so it holds the call open
    without transmitting real audio, until 'VC Start' switches it over to
    the live record/relay pipeline.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SILENCE_PATH) and os.path.getsize(SILENCE_PATH) > 44:
        return SILENCE_PATH

    n_frames = int(sample_rate * duration_sec)
    with wave.open(SILENCE_PATH, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * n_frames * channels * sample_width)

    return SILENCE_PATH
