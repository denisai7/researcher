from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, TypeVar

from src.utils.logging import logger

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0
DEFAULT_MAX_DELAY = 30.0
DEFAULT_JITTER = 0.5  # ±50% jitter


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    jitter: float = DEFAULT_JITTER,
    **kwargs: Any,
) -> Any:
    """Execute an async function with exponential backoff retry and jitter.

    Jitter adds randomness to the delay (±jitter fraction) to prevent
    thundering herd when multiple requests retry simultaneously.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                logger.error(
                    f"All {max_retries + 1} attempts failed for {func.__name__}: {e}"
                )
                raise
            base = min(base_delay * (2**attempt), max_delay)
            jitter_range = base * jitter
            delay = base + random.uniform(-jitter_range, jitter_range)
            delay = max(0.1, delay)  # never go below 0.1s
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
    raise last_exception  # Should never reach here
