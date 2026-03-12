"""Test configuration - mock external dependencies."""

import sys
from unittest.mock import MagicMock

# Mock the supabase module before any imports
supabase_mock = MagicMock()
supabase_mock.create_client = MagicMock()
sys.modules["supabase"] = supabase_mock

# Mock python-telegram-bot
telegram_mock = MagicMock()
sys.modules["telegram"] = telegram_mock
sys.modules["telegram.ext"] = MagicMock()

# Mock notebooklm and its submodules
notebooklm_mock = MagicMock()
sys.modules["notebooklm"] = notebooklm_mock
sys.modules["notebooklm.auth"] = MagicMock()
