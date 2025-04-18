# ratelimiter.py
# imports


import asyncio
import logging
import time
from typing import Optional

import httpx
import requests  # for demonstration only

from server.configmanager import config

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Keeps track of wait times for different services. After a 429, it sets a 'wait-until' time
    (the current time + wait duration) for the given service. Subsequent calls to 'get_limit()'
    return the remaining wait time if it has not elapsed yet, or 0 if no wait is needed.
    """

    def __init__(self, default_wait_times: Optional[dict] = None):
        """
        default_wait_times is expected to be a dictionary
        """
        # Fallback if user doesn't provide defaults
        defaults = {
            "perplexity": 60,
            "openai_tokens": 60,
            "openai_requests": 60,
        }

        self.default_wait_times: dict[str, int] = default_wait_times or defaults

        # Track "wait-until" times for each service
        self.wait_until: dict[str, float] = {
            "perplexity": 0,
            "openai_tokens": 0,
            "openai_requests": 0,
        }

    async def limit(
        self, service: str, response: Optional[httpx.Response] = None
    ) -> None:
        """
        If a 429 is received, set the next valid request time for the service
        using the Retry-After header or a default if that's missing.
        """
        logger.error(f"ALERT: Rate limit exceeded for service '{service}'")
        if service not in self.wait_until:
            raise ValueError(f"Unknown service '{service}'")

        # Either the 'Retry-After' header or the default for that service
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            wait_time = (
                int(retry_after) if retry_after else self.default_wait_times[service]
            )
        else:
            # Default 15 seconds of wait time.
            wait_time = 15

        # Record the future time after which requests can resume
        self.wait_until[service] = time.time() + wait_time

    async def get_limit(self, service: str) -> int:
        """
        Returns the number of seconds left to wait for the given service, or 0 if no wait is needed.
        """
        if service not in self.wait_until:
            logger.error(f"Unknown service for rate limiting'{service}'")
            raise ValueError(f"Unknown service '{service}'")

        now = time.time()
        wait_time_remaining = self.wait_until[service] - now
        if wait_time_remaining > 0:
            return int(wait_time_remaining)
        return 0


_rate_limiter_instance = None


def get_ratelimiter() -> RateLimiter:

    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter(config.get("DEFAULT_WAIT_TIMES"))
    return _rate_limiter_instance
