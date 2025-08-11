import os, time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()                 # load the .env file

# ------------------------------------------------------------------ #
# Simple token-bucket rate-limiter for free-tier quotas
# ------------------------------------------------------------------ #
class RateLimiter:
    def __init__(self, requests_per_minute: int, requests_per_day: int):
        self.rpm  = requests_per_minute
        self.rpd  = requests_per_day
        self._req = []                         # timestamps (sec) for last minute
        self._day = 0                          # daily counter
        self._day_id = time.strftime("%Y-%m-%d")

    def _refresh_day(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._day_id:
            self._day_id = today
            self._day    = 0

    def can_make_request(self) -> bool:
        self._refresh_day()
        if self._day >= self.rpd:                       # daily limit
            return False
        now = time.time()
        self._req = [t for t in self._req if now - t < 60]
        return len(self._req) < self.rpm                # per-min limit

    def record_request(self):
        self._refresh_day()
        self._req.append(time.time())
        self._day += 1

    def wait_time_needed(self) -> Optional[float]:
        if not self._req:
            return None
        return max(0, 60 - (time.time() - min(self._req)))


# ------------------------------------------------------------------ #
# Global configuration – tweak limits here
# ------------------------------------------------------------------ #
class Config:


    GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
    TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    # buffer below official free-tier ceilings
    GEMINI_RATE_LIMITER = RateLimiter(requests_per_minute=4,  requests_per_day=90)
    TAVILY_RATE_LIMITER = RateLimiter(requests_per_minute=90, requests_per_day=800)
