<p align="center">
  <img src="assets/banner.svg" width="800" alt="IGNOU Grade Card Bot">
</p>

A Telegram bot that fetches assignment submission status and grade card marks from IGNOU portals. Just send your enrollment number and program code.

## Features

- **Assignment Status** — Check which assignments are submitted, pending, and submission dates — all from the IGNOU SMS portal.
- **Grade Card** — Course-wise marks including assignment scores, theory, practical, and overall status. Both CBCS (4-year) and non-CBCS (3-year) programs supported.
- **Low Marks Alert** — Courses with theory marks below 35 are flagged separately so you know which ones need re-examination or improvement.
- **Quick Summary** — Completed vs pending course counts at a glance.

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message with usage instructions |
| `/check ENROLLMENT PROGRAM` | Fetches assignment status and grade card |

Example:
```
/check 0123456789 BAEGH
```

CBCS programs (4-year): `BAECH`, `BAEGH`, `BAG`, `BAHDH`, `BAHIH`, `BAPAH`, `BAPCH`, `BAPSH`, `BASOH`, `BAVTM`, `BCOMG`, `BCOMOL`, `BSCANH`, `BSCBCH`, `BSCG`, `BSWG`, `BSWGOL`  
All other programs are non-CBCS (3-year).

## Setup

```
git clone https://github.com/SirYadav1/ignou-gradecard-bot.git
cd ignou-gradecard-bot
pip install -r requirements.txt
```

Create `config.py` with your bot token:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN"
```
Or set the `BOT_TOKEN` environment variable.

```
python bot.py
```

## How it Works

1. User sends `/check 0123456789 BAEGH`
2. Bot scrapes the IGNOU SMS portal for assignment submission data
3. Then scrapes the grade card portal for course-wise marks (navigating the ASP.NET __VIEWSTATE form flow)
4. Both results are formatted and sent back together
5. Courses with theory marks below 35 are highlighted for attention

## Dependencies

- Python 3.8+
- `python-telegram-bot` — Telegram Bot API wrapper
- `requests` — HTTP client
- `beautifulsoup4` — HTML parsing

## License

MIT
