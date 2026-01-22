import time
from fastapi import HTTPException


class RateLimiter:
    def __init__(self, interval_sec=3):
        self.interval = interval_sec
        self.last_submit = {}

    def check(self, student_id):
        now = time.time()
        last = self.last_submit.get(student_id, 0)

        if now - last < self.interval:
            remain = self.interval - (now - last)
            raise HTTPException(429, f"Submit too fast, wait {remain:.1f} sec")

        self.last_submit[student_id] = now


rate_limiter = RateLimiter(3)
