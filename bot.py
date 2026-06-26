import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in config.py or env vars!")
        sys.exit(1)

SMS_URL = "https://isms.ignou.ac.in/changeadmdata/StatusAssignment.asp"
GC_URL = "https://gradecard.ignou.ac.in/"

CBCS_PROGRAMS = ['BAECH','BAEGH','BAG','BAHDH','BAHIH','BAPAH','BAPCH','BAPSH',
                 'BASOH','BAVTM','BCOMG','BCOMOL','BSCANH','BSCBCH','BSCG','BSWG','BSWGOL']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎓 *IGNOU Grade Card & Assignment Bot*\n\n"
        "Main aapki IGNOU assignment status aur grade card dono bata sakta hun!\n\n"
        "*Format:*\n"
        "`/check 1234567890 BAM`\n\n"
        "Bas enrollment number aur program code bhejo!",
        parse_mode='Markdown'
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ *Galat Format!*\nSahi format: `/check 1234567890 BAM`",
                parse_mode='Markdown'
            )
            return

        enrollment = parts[1].strip()
        program = parts[2].strip().upper()

        if not enrollment.isdigit() or len(enrollment) != 10:
            await update.message.reply_text(
                "❌ Enrollment number 10 digits ka hona chahiye!",
                parse_mode='Markdown'
            )
            return

        loading = await update.message.reply_text("⏳ *Loading...*", parse_mode='Markdown')

        assignments = get_assignments(enrollment, program)
        name, gc_data = get_grade_card(enrollment, program)

        if assignments is None and gc_data is None:
            await loading.edit_text("❌ *Record nahi mila!* Enrollment ya program check karo.", parse_mode='Markdown')
            return

        if assignments is None:
            assignments = []

        result = format_output(enrollment, program, name, assignments, gc_data)

        if len(result) > 4000:
            mid = len(result) // 2
            await loading.edit_text(result[:mid], parse_mode='Markdown')
            await update.message.reply_text(result[mid:], parse_mode='Markdown')
        else:
            await loading.edit_text(result, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}", parse_mode='Markdown')

def get_assignments(enrollment, program):
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        session.get(SMS_URL, headers=headers, timeout=30)
        data = {'EnrNo': enrollment, 'program': program, 'Submit': 'Submit'}
        r = session.post(SMS_URL, data=data, headers=headers, timeout=30)

        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        if 'No Record Found' in text or 'Invalid' in text:
            return None

        courses = []
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    c = [x.get_text(strip=True) for x in cells]
                    course = session_val = status = date = ""
                    for ct in c:
                        if len(ct) == 7 and ct.isalnum():
                            course = ct
                        elif any(s in ct for s in ['Jun','Dec','Jan']):
                            session_val = ct
                        elif 'Check Grade' in ct or 'Submitted' in ct:
                            status = ct
                        elif '-' in ct and len(ct) == 11:
                            date = ct
                    if course and course not in [x['code'] for x in courses]:
                        courses.append({
                            'code': course,
                            'session': session_val,
                            'status': status,
                            'date': date
                        })

        return courses if courses else None
    except Exception as e:
        logger.error(f"SMS Error: {e}")
        return None

def get_grade_card(enrollment, program):
    try:
        s = requests.Session()
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        def gf(soup):
            f = {}
            for i in soup.find_all('input'):
                n = i.get('name')
                if n: f[n] = i.get('value', '')
            return f

        prog_type = '4' if program in CBCS_PROGRAMS else '3'

        r = s.get(GC_URL, headers=h, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')

        fields = gf(soup)
        d = {'__EVENTTARGET': 'ddlGradecardfor', '__EVENTARGUMENT': '', '__LASTFOCUS': '',
             '__VIEWSTATE': fields.get('__VIEWSTATE', ''),
             '__VIEWSTATEGENERATOR': fields.get('__VIEWSTATEGENERATOR', ''),
             '__VIEWSTATEENCRYPTED': '', '__EVENTVALIDATION': fields.get('__EVENTVALIDATION', ''),
             'ddlGradecardfor': prog_type, 'ddlProgram': '', 'txtEnrno': ''}
        r = s.post(GC_URL, data=d, headers=h, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')

        fields = gf(soup)
        d = {'__EVENTTARGET': 'ddlProgram', '__EVENTARGUMENT': '', '__LASTFOCUS': '',
             '__VIEWSTATE': fields.get('__VIEWSTATE', ''),
             '__VIEWSTATEGENERATOR': fields.get('__VIEWSTATEGENERATOR', ''),
             '__VIEWSTATEENCRYPTED': '', '__EVENTVALIDATION': fields.get('__EVENTVALIDATION', ''),
             'ddlGradecardfor': prog_type, 'ddlProgram': program, 'txtEnrno': ''}
        r = s.post(GC_URL, data=d, headers=h, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')

        fields = gf(soup)
        d = {'__EVENTTARGET': '', '__EVENTARGUMENT': '', '__LASTFOCUS': '',
             '__VIEWSTATE': fields.get('__VIEWSTATE', ''),
             '__VIEWSTATEGENERATOR': fields.get('__VIEWSTATEGENERATOR', ''),
             '__VIEWSTATEENCRYPTED': '', '__EVENTVALIDATION': fields.get('__EVENTVALIDATION', ''),
             'ddlGradecardfor': prog_type, 'ddlProgram': program,
             'txtEnrno': enrollment, 'btnlogin': 'Search'}
        r = s.post(GC_URL, data=d, headers=h, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')

        name = ""
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = [c.get_text(strip=True) for c in row.find_all('td')]
                if 'Name:' in ' '.join(cells):
                    for i, c in enumerate(cells):
                        if c == 'Name:' and i+1 < len(cells):
                            name = cells[i+1]
                            break

        courses = []
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 2: continue
            hdrs = [c.get_text(strip=True).upper() for c in rows[0].find_all(['th','td'])]

            if 'COURSE' in hdrs and 'STATUS' in hdrs:
                ci = hdrs.index('COURSE')
                si = hdrs.index('STATUS')
                ai = hdrs.index('ASGN1') if 'ASGN1' in hdrs else -1
                ti = hdrs.index('TERM END THEORY') if 'TERM END THEORY' in hdrs else -1
                pi = hdrs.index('TERM END PRACTICAL') if 'TERM END PRACTICAL' in hdrs else -1

                for row in rows[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all('td')]
                    if cells and cells[0] and len(cells) > ci:
                        courses.append({
                            'code': cells[ci],
                            'asgn': cells[ai] if ai != -1 and ai < len(cells) else "-",
                            'theory': cells[ti] if ti != -1 and ti < len(cells) else "-",
                            'practical': cells[pi] if pi != -1 and pi < len(cells) else "-",
                            'status': cells[si] if si < len(cells) else ""
                        })

        return name, courses if courses else None
    except Exception as e:
        logger.error(f"GC Error: {e}")
        return "", None

def format_output(enrollment, program, name, assignments, gc_data):
    result = f"📋 *IGNOU Assignment & Grade Card*\n"
    result += f"━━━━━━━━━━━━━━━━━━\n"
    if name:
        result += f"👤 *Name:* {name}\n"
    result += f"🆔 *Enrollment:* {enrollment}\n"
    result += f"📚 *Program:* {program}\n"
    result += f"━━━━━━━━━━━━━━━━━━\n\n"

    result += f"📝 *Assignment Submission Status:*\n"
    if assignments:
        for a in assignments:
            result += f"✅ *{a['code']}* ({a['session']})\n"
            result += f"   📅 Date: {a['date'] if a['date'] else 'N/A'}\n"
    else:
        result += "✅ All assignments submitted\n"

    result += f"\n📊 *Grade Card - Marks & Status:*\n"
    if gc_data:
        completed = 0
        not_completed = 0
        for c in gc_data:
            is_comp = ('COMPLETED' in c['status'].upper() and 'NOT' not in c['status'].upper())
            status_icon = "✅" if is_comp else "❌"
            if is_comp:
                completed += 1
            else:
                not_completed += 1

            result += f"{status_icon} *{c['code']}*\n"
            result += f"   📝 Asgn: {c['asgn']} | 📖 Theory: {c['theory']}"
            if c['practical'] != "0" and c['practical'] != "-":
                result += f" | 🔬 Practical: {c['practical']}"
            result += f"\n   📊 {c['status']}\n\n"

        result += f"━━━━━━━━━━━━━━━━━━\n"
        result += f"📈 *Summary:* {len(gc_data)} courses | ✅ {completed} Completed | ❌ {not_completed} Not Completed\n"

        low_marks = []
        for c in gc_data:
            if c['theory'] != "-" and c['theory'] != "0":
                try:
                    tm = int(c['theory'])
                    if tm < 35:
                        low_marks.append(f"{c['code']} (Theory: {tm}/100)")
                except:
                    pass

        if low_marks:
            result += f"\n⚠️ *Attention Needed:*\n"
            for lm in low_marks:
                result += f"❌ {lm} — Re-exam/Improvement dena padega!\n"

    result += f"\n🔗 Grade Card: https://gradecard.ignou.ac.in"
    return result

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Format: `/check 1234567890 BAM`",
        parse_mode='Markdown'
    )

def main():
    logger.info("Bot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    logger.info("Bot running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
