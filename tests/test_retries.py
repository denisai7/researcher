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
