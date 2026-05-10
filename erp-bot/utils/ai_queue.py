"""
Priority-based AI request queue.
Uses asyncio.PriorityQueue so premium users get served before standard/free.
"""
import asyncio
from utils.groq_client import GroqClient


# Priority mapping: lower number = higher priority
PRIORITY_MAP = {
    "premium": 1,
    "standard": 2,
    "free": 3,
}


class QItem:
    """Wrapper for queue items to ensure proper ordering by (priority, counter) only."""
    def __init__(self, priority: int, counter: int, future: asyncio.Future, data: dict):
        self.priority = priority
        self.counter = counter
        self.future = future
        self.data = data

    def __lt__(self, other):
        if not isinstance(other, QItem):
            return NotImplemented
        return (self.priority, self.counter) < (other.priority, other.counter)


class AIQueue:
    """
    Async priority queue for AI generation requests.
    Premium users jump ahead of standard/free users.
    """

    def __init__(self, groq_client: GroqClient):
        self.groq = groq_client
        self.queue = asyncio.PriorityQueue()
        self.worker_task = None
        self._counter = 0
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the background worker that processes the queue."""
        self.worker_task = asyncio.create_task(self._worker())
        print("[AIQueue] Worker started")

    async def stop(self):
        """Stop the background worker."""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            self.worker_task = None
            print("[AIQueue] Worker stopped")

    async def enqueue(self, messages: list, temperature: float, max_tokens: int,
                      user_id: int, sub_type: str,
                      disable_refusal_retry: bool = False) -> str:
        """
        Enqueue an AI request with priority based on subscription type.
        Returns the generated text.

        :param disable_refusal_retry: forwarded to GroqClient.generate.
        """
        priority = PRIORITY_MAP.get(sub_type, 3)

        async with self._lock:
            counter = self._counter
            self._counter += 1

        future = asyncio.get_running_loop().create_future()

        item = QItem(priority, counter, future, {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "user_id": user_id,
            "sub_type": sub_type,
            "disable_refusal_retry": disable_refusal_retry,
        })

        await self.queue.put(item)
        print(f"[AIQueue] Enqueued request for user {user_id} (sub={sub_type}, priority={priority}) "
              f"| Queue size: {self.queue.qsize()}")

        try:
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            print(f"[AIQueue] Timeout for user {user_id}")
            raise TimeoutError("AI request timed out after 60s")

    async def _worker(self):
        """Background worker that processes queued AI requests by priority."""
        while True:
            try:
                item = await self.queue.get()

                print(f"[AIQueue] Processing request for user {item.data['user_id']} "
                      f"(sub={item.data['sub_type']}, priority={item.priority}) "
                      f"| Remaining in queue: {self.queue.qsize()}")

                try:
                    result = await self.groq.generate(
                        item.data["messages"],
                        item.data["temperature"],
                        item.data["max_tokens"],
                        disable_refusal_retry=item.data.get("disable_refusal_retry", False),
                    )
                    if not item.future.done():
                        item.future.set_result(result)
                except Exception as e:
                    print(f"[AIQueue] Error processing request: {e}")
                    if not item.future.done():
                        item.future.set_exception(e)

                # Rate limit protection: 0.5s delay between requests
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                # Drain remaining futures on shutdown
                while not self.queue.empty():
                    try:
                        item = self.queue.get_nowait()
                        if not item.future.done():
                            item.future.cancel()
                    except asyncio.QueueEmpty:
                        break
                raise
