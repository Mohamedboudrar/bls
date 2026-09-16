#!/usr/bin/env python3
"""BLS Portugal Morocco deadline monitor."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

URL = "https://www.blsinternational.com/portugal/morocco/"
STATE_PATH = Path(__file__).with_name("state.json")
TIMEOUT_SECONDS = 30

MONTH_PATTERN = r"[A-Za-zÀ-ÿ]+"

DEADLINE_PATTERN = re.compile(
    rf"La\s+prochaine\s+de\s+ces\s+journées\s+aura\s+lieu\s+"
    rf"(le\s+\d{{1,2}}\s+{MONTH_PATTERN}\s+\d{{4}},\s*"
    rf"de\s+\d{{1,2}}h\d{{2}}\s+à\s+\d{{1,2}}h\d{{2}}\.)",
    re.IGNORECASE,
)


@dataclass
class Result:
    url: str
    deadline: Optional[str]
    scraped_at: str
    status: str
    previous_deadline: Optional[str] = None
    error: Optional[str] = None


def normalize(value: str) -> str:
    value = re.sub(r"[\r\n\t]+", " ", str(value))
    value = value.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    return re.sub(r"<[^>]*>", " ", html)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"url": URL, "deadline": None, "last_scraped": None}

    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {
            "url": data.get("url", URL),
            "deadline": data.get("deadline"),
            "last_scraped": data.get("last_scraped"),
        }
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read state.json: {exc}", file=sys.stderr)
        return {"url": URL, "deadline": None, "last_scraped": None}


def save_state(deadline: Optional[str], scraped_at: str) -> None:
    payload = {
        "url": URL,
        "deadline": deadline,
        "last_scraped": scraped_at,
    }
    temporary = STATE_PATH.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(STATE_PATH)


def fetch_deadline() -> tuple[Optional[str], Optional[str]]:
    response = requests.get(
        URL,
        timeout=TIMEOUT_SECONDS,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; BLS-Deadline-Monitor/1.0; "
                "+https://github.com/)"
            )
        },
    )
    response.raise_for_status()

    text = normalize(strip_tags(response.text))
    match = DEADLINE_PATTERN.search(text)

    if not match:
        raise RuntimeError("Deadline marker/date not found in fetched HTML")

    return normalize(match.group(1)), None


def compare(previous: Optional[str], current: Optional[str]) -> str:
    if not current:
        return "ERROR"
    if not previous:
        return "FIRST CHECK"
    if previous == current:
        return "NO CHANGE"
    return "CHANGED"


def format_scraped_time(iso_value: str) -> str:
    try:
        parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        return parsed.strftime("%d %B %Y, %H:%M UTC")
    except ValueError:
        return iso_value


def build_message(result: Result) -> str:
    formatted = format_scraped_time(result.scraped_at)

    if result.status == "CHANGED":
        return "\n".join(
            [
                "🚨 BLS Portugal Morocco — DEADLINE CHANGED",
                "",
                "📅 Scraped:",
                formatted,
                "",
                "❌ Previous:",
                result.previous_deadline or "(none)",
                "",
                "✅ Current:",
                result.deadline or "(none)",
                "",
                f"🔗 {result.url}",
            ]
        )

    if result.status == "ERROR":
        return "\n".join(
            [
                "⚠️ BLS scraper error",
                "",
                "The deadline could not be extracted.",
                "",
                "📅 Scraped:",
                formatted,
                "",
                f"Reason: {result.error or 'unknown'}",
                "",
                f"🔗 {result.url}",
            ]
        )

    if result.status == "FIRST CHECK":
        return "\n".join(
            [
                "🌐 BLS Portugal Morocco",
                "",
                "📅 Scraped:",
                formatted,
                "",
                "⏰ Deadline found:",
                result.deadline or "(none)",
                "",
                "📊 Status:",
                "🆕 FIRST CHECK",
                "",
                f"🔗 {result.url}",
            ]
        )

    return "\n".join(
        [
            "🌐 BLS Portugal Morocco",
            "",
            "📅 Scraped:",
            formatted,
            "",
            "⏰ Deadline found:",
            result.deadline or "(none)",
            "",
            "📊 Status:",
            "🟢 NO CHANGE",
            "",
            f"🔗 {result.url}",
        ]
    )


def send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    raw_chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    if not raw_chat_ids:
        raise RuntimeError("Missing TELEGRAM_CHAT_IDS")

    chat_ids = [item.strip() for item in raw_chat_ids.split(",") if item.strip()]
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in chat_ids:
        response = requests.post(
            endpoint,
            json={
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()


def main() -> int:
    scraped_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous_state = load_state()
    previous_deadline = previous_state.get("deadline")

    try:
        current_deadline, _ = fetch_deadline()
        status = compare(previous_deadline, current_deadline)
        result = Result(
            url=URL,
            deadline=current_deadline,
            scraped_at=scraped_at,
            status=status,
            previous_deadline=previous_deadline,
        )

        # Save only after a successful extraction.
        save_state(current_deadline, scraped_at)

    except Exception as exc:
        result = Result(
            url=URL,
            deadline=None,
            scraped_at=scraped_at,
            status="ERROR",
            previous_deadline=previous_deadline,
            error=str(exc),
        )
        # Preserve the previous state on errors.

    message = build_message(result)
    print(message)

    try:
        send_telegram(message)
    except Exception as exc:
        print(f"Telegram notification failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
