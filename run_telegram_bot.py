#!/usr/bin/env python3
"""
Startup script for the BioRxiv/MedRxiv Telegram Bot.
"""

import os
import sys
import argparse
import logging


def main():
    parser = argparse.ArgumentParser(description="Run BioRxiv/MedRxiv Telegram Bot")
    parser.add_argument(
        "--token",
        type=str,
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)"
    )

    args = parser.parse_args()

    # Set token from argument if provided
    if args.token:
        os.environ["TELEGRAM_BOT_TOKEN"] = args.token

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    # Check for token
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("=" * 60)
        print("BioRxiv/MedRxiv Telegram Bot")
        print("=" * 60)
        print()
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        print()
        print("To create a Telegram bot:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and follow the instructions")
        print("3. Copy the token you receive")
        print()
        print("Then run the bot with:")
        print()
        print("  Option 1: Set environment variable")
        print("    export TELEGRAM_BOT_TOKEN='your_token_here'")
        print("    python run_telegram_bot.py")
        print()
        print("  Option 2: Pass as argument")
        print("    python run_telegram_bot.py --token 'your_token_here'")
        print()
        print("=" * 60)
        sys.exit(1)

    # Import and run bot
    from medrxiv_langchain.telegram_bot import main as run_bot

    print("=" * 60)
    print("BioRxiv/MedRxiv Telegram Bot")
    print("=" * 60)
    print()
    print(f"Log level: {args.log_level}")
    print()
    print("Available commands:")
    print("  /start    - Welcome message")
    print("  /search   - Search for papers")
    print("  /recent   - Get recent papers")
    print("  /help     - Show all commands")
    print()
    print("Starting bot...")
    print()

    run_bot()


if __name__ == "__main__":
    main()
