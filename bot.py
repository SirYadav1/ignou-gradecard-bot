import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import os
import sys
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ignou_bot")

try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN config.py me nahi mila aur env var bhi nahi hai. Bot band.")
        sys.exit(1)

SMS_URL = "https://isms.ignou.ac.in/changeadmdata/StatusAssignment.asp"
GC_URL = "https://gradecard.ignou.ac.in/"

CBCS_PROGRAMS = frozenset({
    "BAECH", "BAEGH", "BAG", "BAHDH", "BAHIH", "BAPAH", "BAPCH", "BAPSH",
    "BASOH", "BAVTM", "BCOMG", "BCOMOL", "BSCANH", "BSCBCH", "BSCG", "BSWG", "BSWGOL",
})

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
}


class IGNOUScraper:
    """Scrapes IGNOU SMS and Grade Card portals for student data."""

    @staticmethod
    def _get_session() -> requests.Session:
        s = requests.Session()
        s.headers.update(HEADERS)
        return s

    @staticmethod
    def _extract_hidden_fields(soup: BeautifulSoup) -> dict:
        """Extracts ASP.NET hidden form fields (__VIEWSTATE, __EVENTVALIDATION, etc.) required for POST requests."""
        fields = {}
        for inp in soup.find_all("input"):
            name = inp.get("name")
            if name:
                fields[name] = inp.get("value", "")
        return fields

    def get_assignments(self, enrollment: str, program: str) -> Optional[list]:
        """Scrapes assignment submission status from the IGNOU SMS portal."""
        try:
            session = self._get_session()
            session.get(SMS_URL, timeout=30)
            data = {"EnrNo": enrollment, "program": program, "Submit": "Submit"}
            r = session.post(SMS_URL, data=data, timeout=30)

            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)

            if "No Record Found" in text or "Invalid" in text:
                return None

            courses = []
            seen = set()
            for table in soup.find_all("table"):
                for row in table.find_all("tr")[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) < 3:
                        continue

                    course = session_val = status = date = ""
                    for ct in cells:
                        if len(ct) == 7 and ct.isalnum():
                            course = ct
                        elif any(s in ct for s in ("Jun", "Dec", "Jan")):
                            session_val = ct
                        elif "Check Grade" in ct or "Submitted" in ct:
                            status = ct
                        elif "-" in ct and len(ct) == 11 and ct[2] == "-" and ct[5] == "-":
                            date = ct

                    if course and course not in seen:
                        seen.add(course)
                        courses.append({
                            "code": course,
                            "session": session_val,
                            "status": status,
                            "date": date,
                        })

            return courses if courses else None

        except requests.RequestException as e:
            logger.warning(f"SMS portal hit karne me problem: {e}")
            return None

    def get_grade_card(self, enrollment: str, program: str) -> tuple:
        """Scrapes student name and course-wise marks from the IGNOU Grade Card portal.

        The ASP.NET __VIEWSTATE dance requires three sequential POST requests
        to navigate the dropdowns and submit the form.
        """
        try:
            session = self._get_session()
            prog_type = "4" if program in CBCS_PROGRAMS else "3"

            # Step 1: select grade card type (CBCS or non-CBCS)
            r = session.get(GC_URL, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")
            fields = self._extract_hidden_fields(soup)

            payload = {
                "__EVENTTARGET": "ddlGradecardfor",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                "__VIEWSTATE": fields.get("__VIEWSTATE", ""),
                "__VIEWSTATEGENERATOR": fields.get("__VIEWSTATEGENERATOR", ""),
                "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": fields.get("__EVENTVALIDATION", ""),
                "ddlGradecardfor": prog_type,
                "ddlProgram": "",
                "txtEnrno": "",
            }
            r = session.post(GC_URL, data=payload, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")

            # Step 2: select the program
            fields = self._extract_hidden_fields(soup)
            payload.update({
                "__EVENTTARGET": "ddlProgram",
                "__VIEWSTATE": fields.get("__VIEWSTATE", ""),
                "__VIEWSTATEGENERATOR": fields.get("__VIEWSTATEGENERATOR", ""),
                "__EVENTVALIDATION": fields.get("__EVENTVALIDATION", ""),
                "ddlGradecardfor": prog_type,
                "ddlProgram": program,
            })
            r = session.post(GC_URL, data=payload, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")

            # Step 3: submit enrollment number
            fields = self._extract_hidden_fields(soup)
            payload.update({
                "__EVENTTARGET": "",
                "__VIEWSTATE": fields.get("__VIEWSTATE", ""),
                "__VIEWSTATEGENERATOR": fields.get("__VIEWSTATEGENERATOR", ""),
                "__EVENTVALIDATION": fields.get("__EVENTVALIDATION", ""),
                "txtEnrno": enrollment,
                "btnlogin": "Search",
            })
            r = session.post(GC_URL, data=payload, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")

            # Extract student name from result table
            name = ""
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in row.find_all("td")]
                    joined = " ".join(cells)
                    if "Name:" in joined:
                        for i, c in enumerate(cells):
                            if c == "Name:" and i + 1 < len(cells):
                                name = cells[i + 1]
                                break

            # Extract course-wise marks from the grade card table
            courses = []
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue

                headers = [c.get_text(strip=True).upper() for c in rows[0].find_all(["th", "td"])]

                if "COURSE" not in headers or "STATUS" not in headers:
                    continue

                ci = headers.index("COURSE")
                si = headers.index("STATUS")
                ai = headers.index("ASGN1") if "ASGN1" in headers else -1
                ti = headers.index("TERM END THEORY") if "TERM END THEORY" in headers else -1
                pi = headers.index("TERM END PRACTICAL") if "TERM END PRACTICAL" in headers else -1

                for row in rows[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all("td")]
                    if not cells or len(cells) <= ci:
                        continue

                    courses.append({
                        "code": cells[ci],
                        "asgn": cells[ai] if ai != -1 and ai < len(cells) else "-",
                        "theory": cells[ti] if ti != -1 and ti < len(cells) else "-",
                        "practical": cells[pi] if pi != -1 and pi < len(cells) else "-",
                        "status": cells[si] if si < len(cells) else "",
                    })

            return name, courses if courses else None

        except requests.RequestException as e:
            logger.warning(f"Grade card portal me problem: {e}")
            return "", None


def format_output(
    enrollment: str,
    program: str,
    name: str,
    assignments: Optional[list],
    gc_data: Optional[list],
) -> str:
    """Formats scraped data into a Telegram-friendly message."""
    lines = []
    lines.append("📋 *IGNOU Assignment & Grade Card*")
    lines.append("━━━━━━━━━━━━━━━━━━")
    if name:
        lines.append(f"👤 *Name:* {name}")
    lines.append(f"🆔 *Enrollment:* {enrollment}")
    lines.append(f"📚 *Program:* {program}")
    lines.append("━━━━━━━━━━━━━━━━━━\n")

    # Assignment status
    lines.append("📝 *Assignment Submission Status:*")
    if assignments:
        for a in assignments:
            date_str = a["date"] if a["date"] else "N/A"
            lines.append(f"✅ *{a['code']}* ({a['session']})")
            lines.append(f"   📅 Date: {date_str}")
    else:
        lines.append("✅ All assignments submitted\n")

    # Grade card
    lines.append("\n📊 *Grade Card - Marks & Status:*")
    if gc_data:
        completed = 0
        not_completed = 0
        low_marks = []

        for c in gc_data:
            is_comp = "COMPLETED" in c["status"].upper() and "NOT" not in c["status"].upper()
            if is_comp:
                completed += 1
            else:
                not_completed += 1

            icon = "✅" if is_comp else "❌"
            lines.append(f"{icon} *{c['code']}*")
            marks = f"   📝 Asgn: {c['asgn']} | 📖 Theory: {c['theory']}"
            if c["practical"] not in ("0", "-"):
                marks += f" | 🔬 Practical: {c['practical']}"
            lines.append(marks)
            lines.append(f"   📊 {c['status']}\n")

            # Low marks checker
            if c["theory"] not in ("-", "0"):
                try:
                    tm = int(c["theory"])
                    if tm < 35:
                        low_marks.append((c["code"], tm))
                except ValueError:
                    pass

        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(
            f"📈 *Summary:* {len(gc_data)} courses"
            f" | ✅ {completed} Completed"
            f" | ❌ {not_completed} Not Completed\n"
        )

        if low_marks:
            lines.append("⚠️ *Attention Needed — Low Theory Marks:*")
            for code, marks in low_marks:
                lines.append(f"❌ {code} (Theory: {marks}/100) — Improvement dena padega!")

    lines.append(f"\n🔗 Grade Card: {GC_URL}")
    return "\n".join(lines)


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 *IGNOU Grade Card & Assignment Bot*\n\n"
        "Apna enrollment number aur program code daalo, main IGNOU se data laakar bata dunga 😎\n\n"
        "*Format:*\n"
        "`/check 1234567890 BAM`\n\n"
        "Example: `/check 0123456789 BAEGH`",
        parse_mode="Markdown",
    )


async def check(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ *Galat hai bhai!*\nSahi tarika: `/check 1234567890 BAM`\n"
                "Enrollment number + program code dono chahiye.",
                parse_mode="Markdown",
            )
            return

        enrollment = parts[1].strip()
        program = parts[2].strip().upper()

        if not enrollment.isdigit() or len(enrollment) != 10:
            await update.message.reply_text(
                "❌ Enrollment number 10 digits ka hota hai. Please check karo!",
                parse_mode="Markdown",
            )
            return

        msg = await update.message.reply_text("⏳ *IGNOU se data le raha hun...*", parse_mode="Markdown")

        scraper = IGNOUScraper()
        assignments = scraper.get_assignments(enrollment, program)
        name, gc_data = scraper.get_grade_card(enrollment, program)

        if assignments is None and gc_data is None:
            await msg.edit_text(
                "❌ *Koi record nahi mila!*\n"
                "Enrollment number ya program code galat ho sakta hai.",
                parse_mode="Markdown",
            )
            return

        result = format_output(enrollment, program, name, assignments or [], gc_data)

        # Telegram max message length is 4096 characters
        if len(result) > 4000:
            mid = len(result) // 2
            await msg.edit_text(result[:mid], parse_mode="Markdown")
            await update.message.reply_text(result[mid:], parse_mode="Markdown")
        else:
            await msg.edit_text(result, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Kuch gadbad ho gayi:")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:200]}",
            parse_mode="Markdown",
        )


async def fallback(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Format: `/check 1234567890 BAM`",
        parse_mode="Markdown",
    )


def main():
    logger.info("Bot start ho raha hai...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))
    logger.info("Bot ready hai! Polling shuru...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
