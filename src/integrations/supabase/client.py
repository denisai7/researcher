from __future__ import annotations

import os
from typing import Any, Optional


_client: Optional[Any] = None


def get_supabase_client() -> Any:
    global _client
    if _client is None:
        from supabase import create_client

        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client
