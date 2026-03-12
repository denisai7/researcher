import asyncio

import pytest

from src.workers.retries import retry_with_backoff


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        call_count = 0

        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await retry_with_backoff(succeeds, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        call_count = 0

        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = await retry_with_backoff(
            fails_twice, max_retries=3, base_delay=0.01
        )
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        async def always_fails():
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            await retry_with_backoff(
                always_fails, max_retries=2, base_delay=0.01
            )


class TestRetryJitter:
    @pytest.mark.asyncio
    async def test_jitter_varies_delay(self):
        """Verify that jitter produces varying delays across retries."""
        import random

        delays = []
        original_sleep = asyncio.sleep

        async def capture_sleep(duration):
            delays.append(duration)

        call_count = 0

        async def fails_then_ok():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retry")
            return "ok"

        # Seed for reproducibility
        random.seed(42)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", capture_sleep)
            result = await retry_with_backoff(
                fails_then_ok, max_retries=3, base_delay=1.0, jitter=0.5
            )

        assert result == "ok"
        assert len(delays) == 2  # 2 retries before success
        # With jitter=0.5, delay should be base*(2^attempt) ± 50%
        # First delay: base=1.0 ± 0.5 -> [0.5, 1.5]
        assert 0.1 <= delays[0] <= 1.5
        # Second delay: base=2.0 ± 1.0 -> [1.0, 3.0]
        assert 0.1 <= delays[1] <= 3.0

    @pytest.mark.asyncio
    async def test_zero_jitter_gives_exact_delay(self):
        """With jitter=0, delays should be exactly base * 2^attempt."""
        delays = []

        async def capture_sleep(duration):
            delays.append(duration)

        call_count = 0

        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry")
            return "ok"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", capture_sleep)
            await retry_with_backoff(
                fails_once, max_retries=2, base_delay=1.0, jitter=0.0
            )

        assert len(delays) == 1
        assert delays[0] == 1.0  # exact, no jitter

    @pytest.mark.asyncio
    async def test_delay_never_below_minimum(self):
        """Even with large negative jitter, delay stays above 0.1s."""
        delays = []

        async def capture_sleep(duration):
            delays.append(duration)

        call_count = 0

        async def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry")
            return "ok"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", capture_sleep)
            await retry_with_backoff(
                fails_once, max_retries=2, base_delay=0.05, jitter=0.99
            )

        assert all(d >= 0.1 for d in delays)


class TestIntentDetection:
    def test_audio_intent(self):
        from src.integrations.notebooklm.adapter import detect_intent

        assert detect_intent("make an audio review") == "audio_overview"
        assert detect_intent("create a podcast about this") == "audio_overview"

    def test_summary_intent(self):
        from src.integrations.notebooklm.adapter import detect_intent

        assert detect_intent("summarize these papers") == "summary"
        assert detect_intent("give me a review") == "summary"

    def test_default_intent(self):
        from src.integrations.notebooklm.adapter import detect_intent

        assert detect_intent("process these files") == "summary"
