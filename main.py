# ============================================================
#  ربات قرآن کریم | نسخه بهینه Async
#  پشته فنی:
#    - aiogram 3.x   → فریم‌ورک استاندارد و مدرن تلگرام (۱۰۰٪ Async)
#    - aiohttp        → کلاینت HTTP غیربلاک‌کننده با Keep-Alive
#    - aiosqlite      → دیتابیس SQLite ناهمگام
#    - json           → ماژول استاندارد و داخلی پایتون (بدون وابستگی اضافی)
#    - uvloop         → موتور پردازش رویدادهای فوق‌سریع در لینوکس/اندروید
#    - async-lru      → کش درون‌حافظه‌ای آیات برای سرعت پاسخ میلی‌ثانیه‌ای
#
#  نسخه: آماده برای دیپلوی روی Runflare (Environment Variables)
# ============================================================


# ==================== ۱. وارد کردن کتابخانه‌ها ====================

import asyncio              # هسته اجرای ناهمگام پایتون
import random               # تولید اعداد تصادفی (برای انتخاب آیات و ایموجی‌ها)
import logging              # سیستم ثبت وقایع و خطاها
import json                 # کتابخانه استاندارد پایتون برای مدیریت فایل‌های JSON
import os                   # تعامل با سیستم‌عامل و بررسی وجود فایل‌ها
import sys                  # برای خروج تمیز از برنامه در صورت نبود تنظیمات ضروری
import time                 # زمان‌سنجی برای کنترل سرعت درخواست کاربران (Rate Limit)

from datetime import datetime, timedelta  # مدیریت تاریخ و زمان برای آمار
from async_lru import alru_cache          # کش کردن توابع Async در رم

# وارد کردن کتابخانه‌های ناهمگام
import aiosqlite            # دیتابیس بدون توقف برنامه
import aiohttp              # درخواست‌های تحت وب بدون ایجاد تاخیر

# تلاش برای فعال‌سازی موتور پرسرعت uvloop (در صورت عدم پشتیبانی سیستم نادیده گرفته می‌شود)
try:
    import uvloop
    uvloop.install()
except (ImportError, AttributeError):
    pass

# ابزارهای مورد نیاز از فریم‌ورک aiogram 3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties  # << جایگزین جدید برای parse_mode در Bot()
from aiogram.types import (
    Message,                # ساختار پیام‌های دریافتی
    CallbackQuery,          # ساختار کلیک روی دکمه‌ها
    InlineKeyboardMarkup,   # ساختار کیبورد شیشه‌ای
    InlineKeyboardButton,   # کلیدهای کیبورد شیشه‌ای
    ReactionTypeEmoji,      # سیستم ارسال واکنش ایموجی
)
from aiogram.filters import Command, CommandStart, Filter  # فیلترهای دریافت دستورات
from aiogram.enums import ParseMode, ChatType      # فرمت‌بندی متن و نوع گفتگو


# ==================== ۲. تنظیمات اصلی ربات (از Environment Variables) ====================

# به‌جای هاردکد کردن توکن و آی‌دی ادمین در کد، این مقادیر از متغیرهای محیطی خوانده می‌شوند.
# این کار باعث می‌شود بتوانی این فایل را روی هر سروری (مثل Runflare) آپلود کنی
# بدون اینکه اطلاعات حساس داخل کد قرار بگیرد یا در معرض دید عموم باشد.

BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ADMIN_IDS باید به‌صورت رشته‌ای از اعداد جدا شده با کاما تعریف شود، مثال:
# ADMIN_IDS=123456789,987654321
_admin_ids_raw = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

DB_FILE = os.environ.get("DB_FILE", "bot_data.db")             # نام فایل پایگاه داده
CONFIG_FILE = os.environ.get("CONFIG_FILE", "bot_config.json") # نام فایل ذخیره تنظیمات متغیر
RATE_LIMIT_SECONDS = int(os.environ.get("RATE_LIMIT_SECONDS", "3"))  # حداقل فاصله مجاز بین درخواست‌های هر کاربر (ثانیه)
API_BASE = "https://api.alquran.cloud/v1/ayah"  # آدرس سرور ارائه‌دهنده اطلاعات قرآن

# بررسی وجود تنظیمات ضروری قبل از اجرای برنامه.
# اگر توکن یا ادمین تعریف نشده باشد، برنامه با یک پیام خطای واضح متوقف می‌شود
# به‌جای اینکه بعداً با یک خطای مبهم از سمت تلگرام کرش کند.
if not BOT_TOKEN:
    print("❌ خطای پیکربندی: متغیر محیطی BOT_TOKEN تعریف نشده است.")
    print("   لطفاً در پنل Runflare بخش Environment Variables مقدار BOT_TOKEN را وارد کنید.")
    sys.exit(1)

if not ADMIN_IDS:
    print("⚠️  هشدار: متغیر محیطی ADMIN_IDS تعریف نشده یا نامعتبر است.")
    print("   ربات اجرا می‌شود اما هیچ‌کس دسترسی ادمین (/stats ، /settings) نخواهد داشت.")


# ==================== ۳. تنظیمات سیستم لاگ ====================

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),  # ذخیره لاگ در فایل
        logging.StreamHandler(),                            # چاپ لاگ در کنسول/ترمینال
    ]
)
logger = logging.getLogger(__name__)


# ==================== ۴. داده‌های اولیه و ثابت‌ها ====================

# فهرست ایموجی‌های مناسب برای واکنش به پیام‌های آیه
REACTIONS = ["🤲", "📖", "💚", "🕌", "✨", "🌙", "❤️", "🙏", "⭐", "💎"]

# کلماتی که اگر در پیام گروه باشند، ربات به آن‌ها پاسخ می‌دهد
TRIGGER_WORDS = [
    "آیه رندوم", "آیه تصادفی", "یه آیه بده", "یک آیه",
    "آیه قرآن", "قرآن رندوم", "آیه بده", "random ayah",
]

# مشخصات و شناسه‌های ترجمه‌های پشتیبانی‌شده در API
AVAILABLE_TRANSLATIONS = {
    "farsi": {
        "fa.makarem": "مکارم شیرازی",
        "fa.fooladvand": "فولادوند",
        "fa.ansarian": "انصاریان",
        "fa.ayati": "آیتی",
        "fa.bahrampour": "بهرام‌پور",
        "fa.gharaati": "قرائتی",
        "fa.khorramshahi": "خرمشاهی",
        "fa.mojtabavi": "مجتبوی",
    },
    "english": {
        "en.sahih": "Sahih International",
        "en.yusufali": "Yusuf Ali",
        "en.pickthall": "Pickthall",
        "en.shakir": "Shakir",
        "en.hilali": "Hilali & Khan",
        "en.clearquran": "Clear Quran",
    },
    "arabic": {
        "ar.alafasy": "العفاسی (با تجوید)",
        "quran-simple": "ساده",
        "quran-uthmani": "عثمانی",
    }
}

# جدول مشخصات ۱۱۴ سوره قرآن: (نام عربی، نام انگلیسی، تعداد کل آیات)
SURAH_LIST = {
    1: ("الفاتحة", "Al-Fatiha", 7), 2: ("البقرة", "Al-Baqarah", 286),
    3: ("آل عمران", "Aal-Imran", 200), 4: ("النساء", "An-Nisa", 176),
    5: ("المائدة", "Al-Ma'idah", 120), 6: ("الأنعام", "Al-An'am", 165),
    7: ("الأعراف", "Al-A'raf", 206), 8: ("الأنفال", "Al-Anfal", 75),
    9: ("التوبة", "At-Tawbah", 129), 10: ("يونس", "Yunus", 109),
    11: ("هود", "Hud", 123), 12: ("يوسف", "Yusuf", 111),
    13: ("الرعد", "Ar-Ra'd", 43), 14: ("إبراهيم", "Ibrahim", 52),
    15: ("الحجر", "Al-Hijr", 99), 16: ("النحل", "An-Nahl", 128),
    17: ("الإسراء", "Al-Isra", 111), 18: ("الكهف", "Al-Kahf", 110),
    19: ("مريم", "Maryam", 98), 20: ("طه", "Ta-Ha", 135),
    21: ("الأنبياء", "Al-Anbiya", 112), 22: ("الحج", "Al-Hajj", 78),
    23: ("المؤمنون", "Al-Mu'minun", 118), 24: ("النور", "An-Nur", 64),
    25: ("الفرقان", "Al-Furqan", 77), 26: ("الشعراء", "Ash-Shu'ara", 227),
    27: ("النمل", "An-Naml", 93), 28: ("القصص", "Al-Qasas", 88),
    29: ("العنكبوت", "Al-Ankabut", 69), 30: ("الروم", "Ar-Rum", 60),
    31: ("لقمان", "Luqman", 34), 32: ("السجدة", "As-Sajdah", 30),
    33: ("الأحزاب", "Al-Ahzab", 73), 34: ("سبأ", "Saba", 54),
    35: ("فاطر", "Fatir", 45), 36: ("يس", "Ya-Sin", 83),
    37: ("الصافات", "As-Saffat", 182), 38: ("ص", "Sad", 88),
    39: ("الزمر", "Az-Zumar", 75), 40: ("غافر", "Ghafir", 85),
    41: ("فصلت", "Fussilat", 54), 42: ("الشورى", "Ash-Shura", 53),
    43: ("الزخرف", "Az-Zukhruf", 89), 44: ("الدخان", "Ad-Dukhan", 59),
    45: ("الجاثية", "Al-Jathiyah", 37), 46: ("الأحقاف", "Al-Ahqaf", 35),
    47: ("محمد", "Muhammad", 38), 48: ("الفتح", "Al-Fath", 29),
    49: ("الحجرات", "Al-Hujurat", 18), 50: ("ق", "Qaf", 45),
    51: ("الذاريات", "Adh-Dhariyat", 60), 52: ("الطور", "At-Tur", 49),
    53: ("النجم", "An-Najm", 62), 54: ("القمر", "Al-Qamar", 55),
    55: ("الرحمن", "Ar-Rahman", 78), 56: ("الواقعة", "Al-Waqi'ah", 96),
    57: ("الحديد", "Al-Hadid", 29), 58: ("المجادلة", "Al-Mujadila", 22),
    59: ("الحشر", "Al-Hashr", 24), 60: ("الممتحنة", "Al-Mumtahina", 13),
    61: ("الصف", "As-Saff", 14), 62: ("الجمعة", "Al-Jumu'ah", 11),
    63: ("المنافقون", "Al-Munafiqun", 11), 64: ("التغابن", "At-Taghabun", 18),
    65: ("الطلاق", "At-Talaq", 12), 66: ("التحريم", "At-Tahrim", 12),
    67: ("الملك", "Al-Mulk", 30), 68: ("القلم", "Al-Qalam", 52),
    69: ("الحاقة", "Al-Haqqah", 52), 70: ("المعارج", "Al-Ma'arij", 44),
    71: ("نوح", "Nuh", 28), 72: ("الجن", "Al-Jinn", 28),
    73: ("المزمل", "Al-Muzzammil", 20), 74: ("المدثر", "Al-Muddaththir", 56),
    75: ("القيامة", "Al-Qiyamah", 40), 76: ("الإنسان", "Al-Insan", 31),
    77: ("المرسلات", "Al-Mursalat", 50), 78: ("النبأ", "An-Naba", 40),
    79: ("النازعات", "An-Nazi'at", 46), 80: ("عبس", "Abasa", 42),
    81: ("التکوير", "At-Takwir", 29), 82: ("الانفطار", "Al-Infitar", 19),
    83: ("المطففين", "Al-Mutaffifin", 36), 84: ("الانشقاق", "Al-Inshiqaq", 25),
    85: ("البروج", "Al-Buruj", 22), 86: ("الطارق", "At-Tariq", 17),
    87: ("الأعلى", "Al-A'la", 19), 88: ("الغاشية", "Al-Ghashiyah", 26),
    89: ("الفجر", "Al-Fajr", 30), 90: ("البلد", "Al-Balad", 20),
    91: ("الشمس", "Ash-Shams", 15), 92: ("الليل", "Al-Layl", 21),
    93: ("الضحى", "Ad-Duha", 11), 94: ("الشرح", "Ash-Sharh", 8),
    95: ("التين", "At-Tin", 8), 96: ("العلق", "Al-Alaq", 19),
    97: ("القدر", "Al-Qadr", 5), 98: ("البينة", "Al-Bayyinah", 8),
    99: ("الزلزلة", "Az-Zalzalah", 8), 100: ("العاديات", "Al-Adiyat", 11),
    101: ("القارعة", "Al-Qari'ah", 11), 102: ("التكاثر", "At-Takathur", 8),
    103: ("العصر", "Al-Asr", 3), 104: ("الهمزة", "Al-Humazah", 9),
    105: ("الفيل", "Al-Fil", 5), 106: ("قريش", "Quraysh", 4),
    107: ("الماعون", "Al-Ma'un", 7), 108: ("الکوثر", "Al-Kawthar", 3),
    109: ("الكافرون", "Al-Kafirun", 6), 110: ("النصر", "An-Nasr", 3),
    111: ("المسد", "Al-Masad", 5), 112: ("الإخلاص", "Al-Ikhlas", 4),
    113: ("الفلق", "Al-Falaq", 5), 114: ("الناس", "An-Nas", 6),
}


# ==================== ۵. کلاس مدیریت تنظیمات (JSON) ====================

class ConfigManager:
    """مدیریت تنظیمات انتخابی ادمین و ذخیره در فایل json با کتابخانه استاندارد پایتون."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        """خواندن تنظیمات از فایل دیسک یا اعمال تنظیمات اولیه."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "farsi_translation": "fa.makarem",
            "english_translation": "en.sahih",
            "arabic_edition": "ar.alafasy",
            "show_farsi": True,
            "show_english": True,
            "show_arabic": True,
            "react_to_ayah": True,
            "footer_text": "🤲 _به نام خداوند بخشنده مهربان_",
        }

    def _save(self):
        """ذخیره دائمی تنظیمات روی فایل با فرمت خوانا."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self._save()


# ==================== ۶. کلاس مدیریت دیتابیس (aiosqlite) ====================

class AsyncStatsManager:
    """مدیریت پایگاه داده SQLite به صورت کاملاً غیرمسدودکننده و ناهمگام."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        """ساخت جداول پایگاه داده در زمان روشن شدن ربات."""
        async with aiosqlite.connect(self.db_path) as db:
            # فعال‌سازی WAL mode برای عملکرد بهتر هم‌زمانی (خواندن و نوشتن هم‌زمان بدون قفل)
            await db.execute("PRAGMA journal_mode=WAL;")
            # busy_timeout: به‌جای شکست فوری روی قفل، تا ۵ ثانیه صبر می‌کند
            await db.execute("PRAGMA busy_timeout=5000;")
            await db.execute("PRAGMA synchronous=NORMAL;")

            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    join_date TEXT,
                    last_request TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    join_date TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    chat_type TEXT,
                    req_type TEXT,
                    surah INTEGER,
                    timestamp TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            await db.execute(
                "INSERT OR IGNORE INTO info (key, value) VALUES ('start_time', ?)",
                (datetime.now().isoformat(),)
            )
            await db.commit()

    async def add_user(self, user_id: int, username: str, first_name: str):
        """ثبت کاربر جدید یا به‌روزرسانی مشخصات کاربر قبلی."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO users (id, username, first_name, join_date, last_request)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_request=excluded.last_request
            ''', (user_id, username, first_name,
                  datetime.now().strftime("%Y-%m-%d"),
                  datetime.now().isoformat()))
            await db.commit()

    async def add_group(self, chat_id: int, title: str):
        """ثبت مشخصات گروه."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO groups (id, title, join_date)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title
            ''', (chat_id, title, datetime.now().strftime("%Y-%m-%d")))
            await db.commit()

    async def add_request(self, user_id: int, chat_id: int,
                          chat_type: str, req_type: str, surah: int = None):
        """ثبت گزارش یک درخواست برای آنالیز آمار."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO requests
                (user_id, chat_id, chat_type, req_type, surah, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, chat_id, chat_type, req_type, surah,
                  datetime.now().isoformat()))
            await db.commit()

    async def get_summary(self) -> str:
        """محاسبه و خروجی متن گزارش جامع آمار."""
        async with aiosqlite.connect(self.db_path) as db:
            total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
            total_groups = (await (await db.execute("SELECT COUNT(*) FROM groups")).fetchone())[0]
            total_req = (await (await db.execute("SELECT COUNT(*) FROM requests")).fetchone())[0]
            random_req = (await (await db.execute(
                "SELECT COUNT(*) FROM requests WHERE req_type='random'")).fetchone())[0]
            specific_req = (await (await db.execute(
                "SELECT COUNT(*) FROM requests WHERE req_type='specific'")).fetchone())[0]
            group_req = (await (await db.execute(
                "SELECT COUNT(*) FROM requests WHERE chat_type='group'")).fetchone())[0]
            private_req = (await (await db.execute(
                "SELECT COUNT(*) FROM requests WHERE chat_type='private'")).fetchone())[0]

            today = datetime.now().strftime("%Y-%m-%d")
            today_req = (await (await db.execute(
                "SELECT COUNT(*) FROM requests WHERE timestamp LIKE ?",
                (f"{today}%",))).fetchone())[0]

            start_row = await (await db.execute(
                "SELECT value FROM info WHERE key='start_time'")).fetchone()
            start_time = start_row[0] if start_row else "نامشخص"

            # محاسبه سوره‌های پرطرفدار
            cursor = await db.execute('''
                SELECT surah, COUNT(*) as cnt FROM requests
                WHERE surah IS NOT NULL GROUP BY surah
                ORDER BY cnt DESC LIMIT 5
            ''')
            popular = await cursor.fetchall()
            popular_text = ""
            for rank, (s_num, count) in enumerate(popular, 1):
                if s_num in SURAH_LIST:
                    ar, en, _ = SURAH_LIST[s_num]
                    popular_text += f"   {rank}. {ar} ({en}) → {count} بار\n"
            if not popular_text:
                popular_text = "   هنوز داده‌ای ثبت نشده\n"

            # محاسبه فعال‌ترین کاربران
            cursor = await db.execute('''
                SELECT u.first_name, u.username, COUNT(r.id) as cnt
                FROM requests r JOIN users u ON r.user_id = u.id
                GROUP BY r.user_id ORDER BY cnt DESC LIMIT 5
            ''')
            active = await cursor.fetchall()
            active_text = ""
            for rank, (fname, uname, cnt) in enumerate(active, 1):
                active_text += f"   {rank}. {fname} (@{uname}) → {cnt}\n" if uname \
                    else f"   {rank}. {fname} → {cnt}\n"
            if not active_text:
                active_text = "   هنوز داده‌ای ثبت نشده\n"

            # محاسبه گروه‌های با بیشترین استفاده
            cursor = await db.execute('''
                SELECT g.title, COUNT(r.id) as cnt
                FROM requests r JOIN groups g ON r.chat_id = g.id
                WHERE r.chat_type='group'
                GROUP BY r.chat_id ORDER BY cnt DESC LIMIT 5
            ''')
            groups_rows = await cursor.fetchall()
            groups_text = ""
            for title, cnt in groups_rows:
                groups_text += f"   ▫️ {title} → {cnt} req\n"
            if not groups_text:
                groups_text = "   هنوز گروهی ثبت نشده\n"

            # رسم نمودار میله‌ای ۷ روز گذشته
            week_stats = ""
            for i in range(6, -1, -1):
                day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                cnt = (await (await db.execute(
                    "SELECT COUNT(*) FROM requests WHERE timestamp LIKE ?",
                    (f"{day}%",))).fetchone())[0]
                bar = "█" * min(cnt, 20)
                week_stats += f"  {day[5:]} {bar} {cnt}\n"

        return (
            f"📊 *آمار کامل ربات قرآن کریم*\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"👥 *کاربران و گروه‌ها:*\n"
            f"   ▫️ کل کاربران: `{total_users}`\n"
            f"   ▫️ کل گروه‌ها: `{total_groups}`\n\n"
            f"📈 *درخواست‌ها:*\n"
            f"   ▫️ کل: `{total_req}`\n"
            f"   ▫️ رندوم: `{random_req}`\n"
            f"   ▫️ مشخص: `{specific_req}`\n"
            f"   ▫️ از گروه: `{group_req}`\n"
            f"   ▫️ از خصوصی: `{private_req}`\n"
            f"   ▫️ امروز: `{today_req}`\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📅 *هفته اخیر:*\n"
            f"```\n{week_stats}```\n\n"
            f"🏆 *محبوب‌ترین سوره‌ها:*\n{popular_text}\n"
            f"⭐ *فعال‌ترین کاربران:*\n{active_text}\n"
            f"🏘 *گروه‌های فعال:*\n{groups_text}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🕐 شروع: {start_time[:10]}"
        )

    async def get_users_list(self) -> list:
        """لیست ۳۰ کاربر با بیشترین درخواست."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.id, u.first_name, u.username, COUNT(r.id)
                FROM users u LEFT JOIN requests r ON u.id = r.user_id
                GROUP BY u.id ORDER BY COUNT(r.id) DESC LIMIT 30
            ''')
            return await cursor.fetchall()


# ==================== ۷. متغیرهای سراسری ====================

config = ConfigManager(CONFIG_FILE)
stats = AsyncStatsManager(DB_FILE)
user_last_request: dict[int, float] = {}

# مجموعه ادمین‌هایی که منتظر ارسال متن جدید پاورقی هستند (برای دکمه «✏️ تغییر پاورقی»)
awaiting_footer: set[int] = set()


class IsAwaitingFooter(Filter):
    """فیلتری که فقط پیام‌های ادمینِ در حالت «انتظار پاورقی» را قبول می‌کند.
    برای بقیه پیام‌ها False برمی‌گرداند تا دیسپچر به هندلر بعدی (handle_text) برود."""
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in awaiting_footer

# کلاینت HTTP ماندگار (Connection Pooling)
http_session: aiohttp.ClientSession | None = None


# ==================== ۸. توابع کمکی ====================

def is_admin(user_id: int) -> bool:
    """بررسی ادمین بودن کاربر."""
    return user_id in ADMIN_IDS


def check_rate_limit(user_id: int) -> bool:
    """جلوگیری از اسپم درخواست‌ها."""
    now = time.time()
    last = user_last_request.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    user_last_request[user_id] = now
    return True


def sanitize_input(text: str) -> str:
    """ایمن‌سازی ورودی‌ها."""
    if not text:
        return text
    for char in ['<', '>', '&', '"', "'", '\\', ';', '|', '$', '`']:
        text = text.replace(char, '')
    return text[:100]


# ==================== ۹. هسته دریافت داده آیه با کش LRU ====================

@alru_cache(maxsize=500)
async def fetch_ayah_json(url: str) -> dict | None:
    """
    دریافت و کش کردن اطلاعات آیه از API.
    پاسخ مستقیماً با aiohttp پارس می‌شود (بدون نیاز به کتابخانه‌های خارجی C/Rust).
    """
    try:
        async with http_session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return await resp.json()  # پارس خودکار JSON
            return None
    except Exception as e:
        logger.error(f"خطا در ارتباط با وب‌سرویس {url}: {e}")
        return None


async def get_ayah(surah: int = None, ayah_num: int = None) -> tuple[str | None, int | None]:
    """
    دریافت همزمان متن عربی، ترجمه فارسی و انگلیسی آیه با استفاده از gather.
    """
    try:
        reference = f"{surah}:{ayah_num}" if surah and ayah_num else random.randint(1, 6236)

        arabic_ed = config.get("arabic_edition", "ar.alafasy")
        farsi_ed = config.get("farsi_translation", "fa.makarem")
        english_ed = config.get("english_translation", "en.sahih")
        show_arabic = config.get("show_arabic", True)
        show_farsi = config.get("show_farsi", True)
        show_english = config.get("show_english", True)
        footer = config.get("footer_text", "🤲 _به نام خداوند بخشنده مهربان_")

        arabic_url = f"{API_BASE}/{reference}/{arabic_ed}"
        farsi_url = f"{API_BASE}/{reference}/{farsi_ed}"
        english_url = f"{API_BASE}/{reference}/{english_ed}"

        # اجرای همزمان و موازی درخواست‌ها در کسری از ثانیه
        tasks = [fetch_ayah_json(arabic_url)]
        tasks.append(fetch_ayah_json(farsi_url) if show_farsi else asyncio.sleep(0, result=None))
        tasks.append(fetch_ayah_json(english_url) if show_english else asyncio.sleep(0, result=None))

        arabic_data, farsi_data, english_data = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        if not arabic_data or isinstance(arabic_data, Exception) or arabic_data.get('code') != 200:
            return None, None

        d = arabic_data['data']
        surah_number = d['surah']['number']

        msg = (
            f"📖 *سوره {d['surah']['name']} ({d['surah']['englishName']})*\n"
            f"📌 سوره {surah_number} ، آیه {d['numberInSurah']}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
        )

        if show_arabic:
            arabic_text = d['text'].replace("`", "'")
            msg += f"🕋 *متن عربی:*\n\n`{arabic_text}`\n\n━━━━━━━━━━━━━━━\n\n"

        if show_farsi and farsi_data and not isinstance(farsi_data, Exception):
            if farsi_data.get('code') == 200:
                fa_name = AVAILABLE_TRANSLATIONS["farsi"].get(farsi_ed, farsi_ed)
                fa_text = farsi_data['data']['text'].replace("`", "'")
                msg += f"🇮🇷 *ترجمه فارسی ({fa_name}):*\n\n`{fa_text}`\n\n━━━━━━━━━━━━━━━\n\n"

        if show_english and english_data and not isinstance(english_data, Exception):
            if english_data.get('code') == 200:
                en_name = AVAILABLE_TRANSLATIONS["english"].get(english_ed, english_ed)
                en_text = english_data['data']['text'].replace("`", "'")
                msg += f"🇬🇧 *{en_name}:*\n\n`{en_text}`\n\n━━━━━━━━━━━━━━━\n\n"

        msg += footer
        return msg, surah_number

    except Exception as e:
        logger.error(f"خطا در تابع get_ayah: {e}")
        return None, None


# ==================== ۱۰. عملیات پس‌زمینه (Background Tasks) ====================

async def add_reaction_safe(message: Message):
    """ثبت واکنش ایموجی با مدیریت خطا."""
    if config.get("react_to_ayah", True):
        try:
            emoji = random.choice(REACTIONS)
            await message.react([ReactionTypeEmoji(emoji=emoji)])
        except Exception:
            pass


async def log_and_react(react_target: Message, chat_type: str, user,
                        chat_id: int, chat_title: str, surah: int, req_type: str):
    """ثبت لاگ و ایموجی در پس‌زمینه بدون معطل کردن کاربر.
    react_target باید پیام خودِ کاربر باشد (نه پیام ربات) تا واکنش روی پیام او ثبت شود."""
    await add_reaction_safe(react_target)
    try:
        if chat_type == "group":
            await stats.add_group(chat_id, chat_title)
        await stats.add_request(user.id, chat_id, chat_type, req_type, surah)
        await stats.add_user(user.id, user.username, user.first_name)
    except Exception as e:
        logger.error(f"خطا در ثبت لاگ پس‌زمینه: {e}")


def get_chat_type(message_or_query) -> str:
    """تشخیص نوع چت (گروه یا چت خصوصی)."""
    if isinstance(message_or_query, CallbackQuery):
        chat = message_or_query.message.chat
    else:
        chat = message_or_query.chat
    return "group" if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) else "private"


# ==================== ۱۱. روتر اصلی رویدادهای ربات ====================

router = Router(name="main")


# ==================== ۱۲. هندلرهای دستورات متنی ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """دستور /start"""
    user = message.from_user
    chat_type = get_chat_type(message)

    if chat_type == "group":
        await message.answer(
            "🕌 سلام! برای آیه رندوم بنویسید: *آیه رندوم*\n"
            "یا از دستور /random استفاده کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    asyncio.create_task(stats.add_user(user.id, user.username, user.first_name))

    buttons = [
        [InlineKeyboardButton(text="🎲 آیه رندوم", callback_data="random")],
        [
            InlineKeyboardButton(text="📚 سوره‌ها ۱-۳۸", callback_data="surah_page_1"),
            InlineKeyboardButton(text="📚 ۳۹-۷۶", callback_data="surah_page_2"),
        ],
        [InlineKeyboardButton(text="📚 ۷۷-۱۱۴", callback_data="surah_page_3")],
        [InlineKeyboardButton(text="❓ راهنما", callback_data="help")],
    ]
    if is_admin(user.id):
        buttons.append([
            InlineKeyboardButton(text="📊 آمار", callback_data="admin_stats"),
            InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="admin_settings"),
        ])

    await message.answer(
        f"🕌 *به ربات قرآن کریم خوش آمدید* 🕌\n\n"
        f"سلام *{user.first_name}* عزیز! 💚\n\n"
        f"🎲 آیات رندوم قرآن\n"
        f"🔍 جستجوی آیه خاص\n"
        f"📖 متن عربی + ترجمه فارسی و انگلیسی\n\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📌 *دستورات:*\n"
        f"▫️ /random - آیه رندوم\n"
        f"▫️ /ayah `2 255` - آیه خاص\n"
        f"▫️ /surah - فهرست سوره‌ها\n"
        f"▫️ /help - راهنما\n\n"
        f"💡 در گروه کلمه *آیه رندوم* را بنویسید!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=ParseMode.MARKDOWN
    )


@router.message(Command("random"))
async def cmd_random(message: Message):
    """دستور /random"""
    user = message.from_user
    chat_type = get_chat_type(message)

    if not check_rate_limit(user.id):
        if chat_type == "private":
            await message.answer("⏳ لطفاً چند ثانیه صبر کنید...")
        return

    waiting_msg = await message.answer("⏳ در حال دریافت آیه...")
    result, surah_num = await get_ayah()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 آیه بعدی", callback_data="random")]
    ])

    if result:
        await waiting_msg.edit_text(result, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(log_and_react(
            message, chat_type, user,
            message.chat.id,
            message.chat.title or "",
            surah_num, "random"
        ))
    else:
        await waiting_msg.edit_text("❌ خطا! دوباره تلاش کنید.", reply_markup=keyboard)


@router.message(Command("ayah"))
async def cmd_ayah(message: Message, command: Command):
    """دستور /ayah برای فراخوانی آیه خاص: مثال /ayah 2 255"""
    user = message.from_user
    chat_type = get_chat_type(message)

    if not check_rate_limit(user.id):
        if chat_type == "private":
            await message.answer("⏳ صبر کنید...")
        return

    args = command.args
    if not args or len(args.split()) != 2:
        await message.answer(
            "❌ *فرمت:* `/ayah شماره_سوره شماره_آیه`\n\n"
            "مثال: `/ayah 2 255`\nفهرست سوره‌ها: /surah",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        parts = args.split()
        surah = int(sanitize_input(parts[0]))
        ayah = int(sanitize_input(parts[1]))

        if surah < 1 or surah > 114:
            await message.answer("❌ شماره سوره باید بین ۱ تا ۱۱۴ باشد.")
            return

        if surah in SURAH_LIST:
            max_ayah = SURAH_LIST[surah][2]
            if ayah < 1 or ayah > max_ayah:
                await message.answer(f"❌ سوره {SURAH_LIST[surah][0]} فقط {max_ayah} آیه دارد.")
                return

        waiting_msg = await message.answer("⏳ در حال دریافت...")
        result, _ = await get_ayah(surah, ayah)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 آیه رندوم", callback_data="random")]
        ])

        if result:
            await waiting_msg.edit_text(result, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            asyncio.create_task(log_and_react(
                message, chat_type, user,
                message.chat.id, message.chat.title or "",
                surah, "specific"
            ))
        else:
            await waiting_msg.edit_text("❌ آیه یافت نشد.", reply_markup=keyboard)

    except ValueError:
        await message.answer("❌ لطفاً فقط عدد انگلیسی وارد کنید: `/ayah 2 255`", parse_mode=ParseMode.MARKDOWN)


@router.message(Command("surah"))
async def cmd_surah(message: Message):
    """دستور /surah برای نمایش فهرست سوره‌ها"""
    if get_chat_type(message) == "group":
        await message.answer("📚 فهرست کامل سوره‌ها فقط در چت خصوصی ربات در دسترس است.")
        return

    if not check_rate_limit(message.from_user.id):
        return

    await send_surah_page(message, page=1)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """دستور /help"""
    if get_chat_type(message) == "group":
        await message.answer(
            "📚 *راهنمای سریع:*\n\n"
            "▫️ *آیه رندوم* ← ارسال در چت\n"
            "▫️ /random ← آیه رندوم\n"
            "▫️ /ayah 2 255 ← آیه خاص\n",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await message.answer(
        "📚 *راهنمای ربات قرآن کریم*\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📌 *دستورات:*\n\n"
        "▫️ /start - شروع\n"
        "▫️ /random - آیه رندوم\n"
        "▫️ /ayah `سوره آیه` - آیه خاص\n"
        "▫️ /surah - فهرست ۱۱۴ سوره\n"
        "▫️ /help - راهنما\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📖 *مثال‌ها:*\n\n"
        "▫️ `/ayah 2 255` → آیة‌الکرسی\n"
        "▫️ `/ayah 36 58` → سلام قولاً من رب رحیم\n"
        "▫️ `/ayah 94 5` → إن مع العسر یسرا\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🏘 *در گروه:*\n"
        "فقط کلمه *آیه رندوم* بنویسید!\n"
        "ربات به سایر پیام‌ها هیچ پاسخی نمی‌دهد.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 آیه رندوم", callback_data="random")],
            [InlineKeyboardButton(text="📚 فهرست سوره‌ها", callback_data="surah_page_1")],
        ]),
        parse_mode=ParseMode.MARKDOWN
    )


# ==================== ۱۳. دستورات مخصوص مدیر ====================

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """دستور /stats"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ این بخش مختص مدیریت ربات است.")
        return

    summary = await stats.get_summary()
    await message.answer(
        summary,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📋 کاربران", callback_data="admin_users")],
            [InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="admin_settings")],
        ]),
        parse_mode=ParseMode.MARKDOWN
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """دستور /settings"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ این بخش مختص مدیریت ربات است.")
        return
    await send_settings_menu(message)


# ==================== ۱۴. پردازش پیام‌های متنی عادی و کلمات کلیدی ====================

@router.message(F.text, IsAwaitingFooter())
async def handle_footer_input(message: Message):
    """دریافت متن جدید پاورقی از ادمینی که روی «✏️ تغییر پاورقی» زده است."""
    admin_id = message.from_user.id

    if message.text.strip() == "/cancel":
        awaiting_footer.discard(admin_id)
        await message.answer("❌ لغو شد. پاورقی تغییر نکرد.")
        return

    new_footer = message.text.strip()
    if not new_footer:
        await message.answer("⚠️ متن نمی‌تواند خالی باشد. دوباره بفرستید یا /cancel کنید.")
        return

    config.set("footer_text", new_footer)
    fetch_ayah_json.cache_clear()  # پاک‌سازی کش تا پاورقی جدید در آیات بعدی اعمال شود
    awaiting_footer.discard(admin_id)

    await message.answer(
        f"✅ پاورقی جدید ذخیره شد:\n\n{new_footer}",
        parse_mode=ParseMode.MARKDOWN
    )


@router.message(F.text)
async def handle_text(message: Message):
    """پردازش متن پیام‌های کاربران در گروه و خصوصی."""
    if not message.text:
        return

    text = message.text.strip()
    user = message.from_user
    chat_type = get_chat_type(message)

    # بررسی تطابق پیام با کلمات کلیدی
    is_trigger = any(trigger in text for trigger in TRIGGER_WORDS)

    if not is_trigger:
        # سکوت مطلق در گروه‌ها برای جلوگیری از مزاحمت
        if chat_type == "group":
            return
        await message.answer(
            "🤔 دستور نامعتبر!\n\n"
            "▫️ /random → آیه رندوم\n"
            "▫️ /ayah 2 255 → آیه خاص\n"
            "▫️ /help → راهنما\n\n"
            "یا بنویسید: *آیه رندوم*",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if not check_rate_limit(user.id):
        if chat_type == "private":
            await message.answer("⏳ صبر کنید...")
        return

    waiting_msg = await message.answer("⏳ در حال دریافت آیه...")
    result, surah_num = await get_ayah()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 آیه بعدی", callback_data="random")]
    ])

    if result:
        await waiting_msg.edit_text(result, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(log_and_react(
            message, chat_type, user,
            message.chat.id, message.chat.title or "",
            surah_num, "random"
        ))
    else:
        await waiting_msg.edit_text("❌ خطا!", reply_markup=keyboard)


# ==================== ۱۵. هندلرهای دکمه‌های شیشه‌ای ====================

@router.callback_query(F.data == "random")
async def cb_random(callback: CallbackQuery):
    await callback.answer()
    user = callback.from_user
    chat_type = get_chat_type(callback)

    if not check_rate_limit(user.id):
        await callback.answer("⏳ صبر کنید...", show_alert=True)
        return

    result, surah_num = await get_ayah()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 آیه بعدی", callback_data="random")]
    ])

    if result:
        # چون این درخواست از طریق کلیک روی دکمه است (نه پیام متنی جدید کاربر)،
        # واکنش روی همان پیامِ قبلیِ حاوی دکمه ثبت می‌شود که کاربر با آن تعامل داشته.
        react_target = callback.message
        await callback.message.answer(result, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(log_and_react(
            react_target, chat_type, user,
            callback.message.chat.id, callback.message.chat.title or "",
            surah_num, "random"
        ))
    else:
        await callback.message.answer("❌ خطا!", reply_markup=keyboard)


@router.callback_query(F.data.startswith("surah_page_"))
async def cb_surah_page(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    await send_surah_page(callback.message, page, is_edit=True)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📚 *راهنما:*\n\n"
        "▫️ /random → آیه رندوم\n"
        "▫️ /ayah 2 255 → آیه خاص\n"
        "▫️ در گروه: *آیه رندوم*",
        parse_mode=ParseMode.MARKDOWN
    )


# --- منوهای ادمین ---

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ عدم دسترسی", show_alert=True)
        return

    summary = await stats.get_summary()
    await callback.message.edit_text(
        summary,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📋 کاربران", callback_data="admin_users")],
            [InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="admin_settings")],
        ]),
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return

    rows = await stats.get_users_list()
    text = "👥 *کاربران فعال (تا ۳۰ نفر):*\n\n"
    for rank, (uid, fname, uname, reqs) in enumerate(rows, 1):
        text += f"{rank}. `{uid}` {fname} @{uname} ({reqs})\n" if uname \
            else f"{rank}. `{uid}` {fname} ({reqs})\n"
    if not rows:
        text += "هنوز کاربری ثبت نشده است."
    await callback.message.answer(text, parse_mode=ParseMode.MARKDOWN)


@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    await send_settings_menu(callback.message, is_edit=True)


# --- تنظیمات ترجمه‌ها و پاک‌سازی کش ---

@router.callback_query(F.data == "set_farsi")
async def cb_set_farsi(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    current = config.get("farsi_translation")
    kb = [[InlineKeyboardButton(
        text=f"{name}{' ✅' if k == current else ''}",
        callback_data=f"farsi_{k}"
    )] for k, name in AVAILABLE_TRANSLATIONS["farsi"].items()]
    kb.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="admin_settings")])
    await callback.message.edit_text(
        "🇮🇷 *انتخاب ترجمه فارسی:*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(F.data.startswith("farsi_"))
async def cb_pick_farsi(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    key = callback.data[6:]
    config.set("farsi_translation", key)
    fetch_ayah_json.cache_clear()  # پاک‌سازی کش آیات برای اعمال ترجمه جدید
    await callback.answer(f"✅ {AVAILABLE_TRANSLATIONS['farsi'].get(key)}", show_alert=True)
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "set_english")
async def cb_set_english(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    current = config.get("english_translation")
    kb = [[InlineKeyboardButton(
        text=f"{name}{' ✅' if k == current else ''}",
        callback_data=f"english_{k}"
    )] for k, name in AVAILABLE_TRANSLATIONS["english"].items()]
    kb.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="admin_settings")])
    await callback.message.edit_text(
        "🇬🇧 *انتخاب ترجمه انگلیسی:*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(F.data.startswith("english_"))
async def cb_pick_english(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    key = callback.data[8:]
    config.set("english_translation", key)
    fetch_ayah_json.cache_clear()
    await callback.answer(f"✅ {AVAILABLE_TRANSLATIONS['english'].get(key)}", show_alert=True)
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "set_arabic")
async def cb_set_arabic(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    current = config.get("arabic_edition")
    kb = [[InlineKeyboardButton(
        text=f"{name}{' ✅' if k == current else ''}",
        callback_data=f"arabic_{k}"
    )] for k, name in AVAILABLE_TRANSLATIONS["arabic"].items()]
    kb.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="admin_settings")])
    await callback.message.edit_text(
        "🕋 *انتخاب نسخه عربی:*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(F.data.startswith("arabic_"))
async def cb_pick_arabic(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    key = callback.data[7:]
    config.set("arabic_edition", key)
    fetch_ayah_json.cache_clear()
    await callback.answer(f"✅ {AVAILABLE_TRANSLATIONS['arabic'].get(key)}", show_alert=True)
    await send_settings_menu(callback.message, is_edit=True)


# --- دکمه‌های سوئیچ بخش‌ها ---

@router.callback_query(F.data == "toggle_farsi")
async def cb_toggle_farsi(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    config.set("show_farsi", not config.get("show_farsi", True))
    fetch_ayah_json.cache_clear()
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "toggle_english")
async def cb_toggle_english(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    config.set("show_english", not config.get("show_english", True))
    fetch_ayah_json.cache_clear()
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "toggle_arabic")
async def cb_toggle_arabic(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    config.set("show_arabic", not config.get("show_arabic", True))
    fetch_ayah_json.cache_clear()
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "toggle_react")
async def cb_toggle_react(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    config.set("react_to_ayah", not config.get("react_to_ayah", True))
    await send_settings_menu(callback.message, is_edit=True)


@router.callback_query(F.data == "set_footer")
async def cb_set_footer(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    awaiting_footer.add(callback.from_user.id)
    await callback.message.answer(
        "✏️ *متن جدید پاورقی را بفرستید:*\n\n"
        f"متن کنونی:\n`{config.get('footer_text')}`\n\n"
        "برای لغو عبارت /cancel را بفرستید.",
        parse_mode=ParseMode.MARKDOWN
    )


# ==================== ۱۶. ساخت پیام‌های تعاملی ====================

async def send_surah_page(target: Message, page: int, is_edit: bool = False):
    pages = {1: (1, 38), 2: (39, 76), 3: (77, 114)}
    start_s, end_s = pages.get(page, (1, 38))

    text = f"📚 *فهرست سوره‌ها ({start_s} تا {end_s})*\n\n"
    for i in range(start_s, end_s + 1):
        if i in SURAH_LIST:
            ar, en, cnt = SURAH_LIST[i]
            text += f"`{i:>3}.` {ar} | {en} | {cnt} آیه\n"
    text += "\n💡 `/ayah شماره_سوره شماره_آیه`"

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"surah_page_{page-1}"))
    if page < 3:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"surah_page_{page+1}"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [InlineKeyboardButton(text="🎲 آیه رندوم", callback_data="random")]
    ])

    if is_edit:
        await target.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def send_settings_menu(target: Message, is_edit: bool = False):
    farsi_ed = config.get("farsi_translation", "fa.makarem")
    english_ed = config.get("english_translation", "en.sahih")
    arabic_ed = config.get("arabic_edition", "ar.alafasy")
    show_fa = "✅" if config.get("show_farsi", True) else "❌"
    show_en = "✅" if config.get("show_english", True) else "❌"
    show_ar = "✅" if config.get("show_arabic", True) else "❌"
    react = "✅" if config.get("react_to_ayah", True) else "❌"

    fa_name = AVAILABLE_TRANSLATIONS["farsi"].get(farsi_ed, farsi_ed)
    en_name = AVAILABLE_TRANSLATIONS["english"].get(english_ed, english_ed)
    ar_name = AVAILABLE_TRANSLATIONS["arabic"].get(arabic_ed, arabic_ed)

    text = (
        f"⚙️ *تنظیمات ربات*\n\n━━━━━━━━━━━━━━━\n\n"
        f"🇮🇷 ترجمه فارسی: *{fa_name}*\n"
        f"🇬🇧 ترجمه انگلیسی: *{en_name}*\n"
        f"🕋 نسخه عربی: *{ar_name}*\n\n"
        f"نمایش عربی: {show_ar}\n"
        f"نمایش فارسی: {show_fa}\n"
        f"نمایش انگلیسی: {show_en}\n"
        f"واکنش به آیه: {react}\n\n━━━━━━━━━━━━━━━"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🇮🇷 ترجمه فارسی: {fa_name}", callback_data="set_farsi")],
        [InlineKeyboardButton(text=f"🇬🇧 ترجمه انگلیسی: {en_name}", callback_data="set_english")],
        [InlineKeyboardButton(text=f"🕋 نسخه عربی: {ar_name}", callback_data="set_arabic")],
        [
            InlineKeyboardButton(text=f"عربی {show_ar}", callback_data="toggle_arabic"),
            InlineKeyboardButton(text=f"فارسی {show_fa}", callback_data="toggle_farsi"),
            InlineKeyboardButton(text=f"انگلیسی {show_en}", callback_data="toggle_english"),
        ],
        [InlineKeyboardButton(text=f"واکنش {react}", callback_data="toggle_react")],
        [InlineKeyboardButton(text="✏️ تغییر پاورقی", callback_data="set_footer")],
        [InlineKeyboardButton(text="🔙 برگشت به آمار", callback_data="admin_stats")],
    ])

    if is_edit:
        await target.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


# ==================== ۱۷. رویدادهای Lifecycle ====================

async def on_startup(bot: Bot):
    """راه‌اندازی نشست سراسری وب و دیتابیس در زمان استارت ربات."""
    global http_session
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    http_session = aiohttp.ClientSession(
        connector=connector,
        headers={"Accept": "application/json"}
    )
    await stats.init_db()
    logger.info("✅ دیتابیس و کلاینت aiohttp آماده شدند.")


async def on_shutdown(bot: Bot):
    """بستن ایمن نشست وب جهت جلوگیری از نشت حافظه."""
    global http_session
    if http_session and not http_session.closed:
        await http_session.close()
    logger.info("🔒 نشست وب بسته شد.")


# ==================== ۱۸. اجرای برنامه ====================

async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)  # << فیکس اصلی برای aiogram 3.7+
    )

    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("🚀 ربات در حال اجرا است...")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ✅ ربات قرآن کریم (Aiogram 3 Async)")
    print("  ⚡ aiohttp + aiosqlite + LRU Cache")
    print("  📦 پارسر: ماژول استاندارد json پایتون")
    print(f"  👤 تعداد مدیران تعریف‌شده: {len(ADMIN_IDS)}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    asyncio.run(main())

