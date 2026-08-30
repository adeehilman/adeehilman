"""Entry point: `python -m tiktok_bot <command>`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import runner
from .config import ConfigError, Settings
from .logging_setup import setup_logging
from .session import SessionError, encode_for_secret

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiktok_bot",
        description="Scrape your TikTok following list and send stickers, slowly and on purpose.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="verify the stored session is still logged in")

    scrape_parser = sub.add_parser("scrape", help="collect the accounts you follow")
    scrape_parser.add_argument(
        "--limit", type=int, default=0, help="stop after N accounts (0 = all)"
    )

    send_parser = sub.add_parser("send", help="send the configured sticker to eligible accounts")
    send_parser.add_argument(
        "--only",
        nargs="+",
        metavar="HANDLE",
        help="restrict the run to these handles (still subject to every filter)",
    )
    send_parser.add_argument(
        "--rescrape",
        action="store_true",
        help="refresh the following list instead of reusing out/following.json",
    )

    sub.add_parser("status", help="show what has already been messaged")

    encode_parser = sub.add_parser(
        "encode-session", help="print base64 of a session file, for the CI secret"
    )
    encode_parser.add_argument("path", nargs="?", help="defaults to TIKTOK_SESSION_FILE")

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)

    try:
        settings = Settings.from_env()

        if args.command == "check":
            return runner.check(settings)
        if args.command == "scrape":
            return runner.scrape(settings, limit=args.limit)
        if args.command == "send":
            return runner.send(settings, only=args.only, rescrape=args.rescrape)
        if args.command == "status":
            return runner.status(settings)
        if args.command == "encode-session":
            path = settings.session_file if args.path is None else Path(args.path)
            print(encode_for_secret(path))
            return 0
    except (ConfigError, SessionError) as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        log.warning("interrupted")
        return 130

    return 2


if __name__ == "__main__":
    sys.exit(main())
