import asyncio

class IntervalRunner:
    def __init__(self):
        self.tasks = {}

    async def _interval_loop(self, key, interval, callback):
        try:
            while True:
                await asyncio.sleep(interval)
                await callback()
        except asyncio.CancelledError:
            print(f"Interval '{key}' cancelled.")

    def start_interval(self, key, interval, callback):
        if key in self.tasks:
            print(f"Interval '{key}' already running.")
            return
        task = asyncio.create_task(self._interval_loop(key, interval, callback))
        self.tasks[key] = task

    def stop_interval(self, key):
        task = self.tasks.get(key)
        if task:
            task.cancel()
            del self.tasks[key]

    def stop_all(self):
        for key in list(self.tasks.keys()):
            self.stop_interval(key)