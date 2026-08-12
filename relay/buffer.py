import asyncio
import time


class JitterBuffer:
    """
    In-memory cross-platform Jitter Buffer using asyncio.Queue.
    Provides startup delay cushion, smooth playback, and overflow protection.
    """
    def __init__(self, target_delay_sec: float = 2.0, max_delay_sec: float = 5.0, frame_duration_sec: float = 0.02):
        self.target_delay_sec = target_delay_sec
        self.max_delay_sec = max_delay_sec
        self.frame_duration_sec = frame_duration_sec

        self.target_chunks = int(target_delay_sec / frame_duration_sec)
        self.max_chunks = int(max_delay_sec / frame_duration_sec)

        self._queue = asyncio.Queue()
        self.is_buffering = True
        self.total_received = 0
        self.total_played = 0
        self.total_dropped = 0
        self.start_time = None

    def set_target_delay(self, seconds: float):
        """Dynamically update target delay."""
        self.target_delay_sec = max(0.2, seconds)
        self.target_chunks = int(self.target_delay_sec / self.frame_duration_sec)

    async def put(self, chunk: bytes):
        """Enqueue incoming PCM frame chunk."""
        if self.start_time is None:
            self.start_time = time.time()

        self.total_received += 1

        # Overflow protection: drop oldest frame if buffer exceeds max_chunks
        if self._queue.qsize() >= self.max_chunks:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self.total_dropped += 1
            except asyncio.QueueEmpty:
                pass

        await self._queue.put(chunk)

    async def get(self) -> bytes:
        """Fetch next PCM frame chunk for playback."""
        chunk = await self._queue.get()
        self._queue.task_done()
        self.total_played += 1
        return chunk

    async def wait_for_cushion(self):
        """Wait until buffer reaches target delay cushion before playback starts."""
        self.is_buffering = True
        while self._queue.qsize() < self.target_chunks:
            await asyncio.sleep(0.01)
        self.is_buffering = False

    def get_stats(self) -> dict:
        """Return real-time status metrics."""
        qsize = self._queue.qsize()
        buffered_sec = qsize * self.frame_duration_sec
        uptime = time.time() - self.start_time if self.start_time else 0.0

        return {
            "buffered_chunks": qsize,
            "buffered_seconds": round(buffered_sec, 2),
            "target_delay_seconds": self.target_delay_sec,
            "max_delay_seconds": self.max_delay_sec,
            "is_buffering": self.is_buffering,
            "total_received": self.total_received,
            "total_played": self.total_played,
            "total_dropped": self.total_dropped,
            "uptime_seconds": round(uptime, 1)
        }

    def clear(self):
        """Flush buffer contents."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.is_buffering = True
        self.total_received = 0
        self.total_played = 0
        self.total_dropped = 0
        self.start_time = None
