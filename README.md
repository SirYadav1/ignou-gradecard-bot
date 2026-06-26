<p align="center">
  <img src="assets/banner.svg" width="800" alt="IGNOU Grade Card Bot">
</p>

<p align="center">
  A Telegram bot to check IGNOU assignment submission status and grade cards instantly using enrollment number and program code.
</p>

## Features

- **Assignment Status** — Fetches assignment submission status from the IGNOU Student Management System (SMS).
- **Grade Card** — Retrieves detailed grade card with marks for each course — assignment scores, theory marks, practical marks, and overall status.
- **CBCS Support** — Handles both CBCS (4-year) and non-CBCS (3-year) program types automatically.
- **Mark Analysis** — Highlights courses with marks below passing threshold that may need re-examination.
- **Quick Summary** — Shows completed vs pending course counts at a glance.
- **No database required** — Stateless design; fetches fresh data from IGNOU on each request.

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message with usage instructions |
| `/check ENROLLMENT PROGRAM` | Check assignment status and grade card |

### Usage

```
/check 1234567890 BAM
```

Replace `1234567890` with your 10-digit enrollment number and `BAM` with your program code.

**Supported program types:**
- CBCS programs (4-year): `BAECH`, `BAEGH`, `BAG`, `BAHDH`, `BAHIH`, `BAPAH`, `BAPCH`, `BAPSH`, `BASOH`, `BAVTM`, `BCOMG`, `BCOMOL`, `BSCANH`, `BSCBCH`, `BSCG`, `BSWG`, `BSWGOL`
- Non-CBCS programs (3-year): All other programs

## Setup

1. **Clone the repository**

```bash
git clone https://github.com/SirYadav1/ignou-gradecard-bot.git
cd ignou-gradecard-bot
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure**

Create a `config.py` file with your bot token:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```

Alternatively, set the `BOT_TOKEN` environment variable.

4. **Run**

```bash
python bot.py
```

## Configuration

Configuration is loaded in the following order of precedence:

1. `config.py` in the project root (recommended)
2. `BOT_TOKEN` environment variable

The `config.py` file is excluded from version control via `.gitignore`.

## How it Works

1. User sends `/check ENROLLMENT PROGRAM`.
2. Bot scrapes the IGNOU SMS portal to fetch assignment submission records.
3. Bot scrapes the IGNOU Grade Card portal for detailed course-wise marks.
4. Results are formatted and returned with a summary of completed and pending courses.
5. Courses with theory marks below 35 are flagged for attention.

## Data Sources

- **Assignments**: `isms.ignou.ac.in/changeadmdata/StatusAssignment.asp`
- **Grade Card**: `gradecard.ignou.ac.in`

## Tech Stack

- **Python 3.8+**
- **python-telegram-bot** — Telegram Bot API framework
- **Requests** — HTTP client
- **BeautifulSoup4** — HTML parsing

## License

MIT
