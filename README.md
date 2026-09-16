# BLS Portugal Morocco — Deadline Monitor

A GitHub Actions Python monitor that checks the BLS Portugal Morocco page, extracts the next  open-day deadline, compares it with persistent state, and sends Telegram notifications.

## Features

- Runs on GitHub Actions on a schedule
- Manual execution with `workflow_dispatch`
- Persistent state committed to the repository
- Detects `FIRST CHECK`, `NO CHANGE`, `CHANGED`, and `ERROR`
- Sends Telegram notifications
- Uses the Casablanca timezone for display and scheduling context
- Does not overwrite the saved deadline when scraping fails

## Setup

1. Create a GitHub repository.
2. Copy these files into the repository.
3. Create a Telegram bot using `@BotFather`.
4. Add repository secrets:

   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_IDS` — comma-separated IDs, for example:
     `8038835222,1860534832`

5. Commit and push.
6. Run the workflow once manually from the **Actions** tab.

The first successful run creates `state.json`. Later runs compare the current deadline against that value.

## Schedule

The included schedule runs every day at 13:36 UTC, which is 14:36 in Casablanca during standard time and may differ during daylight-saving changes. Change the cron expression in `.github/workflows/monitor.yml` if you need a different UTC time.

For frequent monitoring, use a cron such as:

```yaml
- cron: "*/15 * * * *"
```

GitHub may delay scheduled workflows, especially during high load. Scheduled workflows are not guaranteed to run at an exact minute.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_IDS="8038835222,1860534832"

python monitor.py
```

On Windows PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN="your-token"
$env:TELEGRAM_CHAT_IDS="8038835222,1860534832"
python monitor.py
```

## Notes

- The parser intentionally looks for the French sentence used by the original n8n workflow.
- If BLS changes the wording or page structure, the script reports `ERROR` and keeps the previous state.
- Never commit your Telegram bot token.
