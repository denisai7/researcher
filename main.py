#!/usr/bin/env python3
"""Researcher Agent -- Telegram bot for NotebookLM-powered research."""

import os
import sys

from dotenv import load_dotenv


def main():
    load_dotenv()

    required_vars = ["TELEGRAM_BOT_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    from src.telegram.bot import ResearcherBot

    bot = ResearcherBot()
    bot.run()


if __name__ == "__main__":
    main()
