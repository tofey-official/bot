import asyncio
import aiohttp
import logging
import re
import ssl
import math
import io
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db
from config import ITEMS_PER_PAGE, MAX_CONCURRENT, REQUEST_TIMEOUT, MAX_HISTORY

logger = logging.getLogger(__name__)

# ==================== دوال مساعدة ====================
def extract_account_info(link: str):
    try:
        parsed = urlparse(link)
        if not parsed.hostname:
            return None
        port = f":{parsed.port}" if parsed.port else ""
        domain = f"{parsed.scheme}://{parsed.hostname}{port}"
        qs = parse_qs(parsed.query)
        username = qs.get("username", [None])[0]
        password = qs.get("password", [None])[0]
        if not username or not password:
            return None
        return domain, username, password
    except Exception as e:
        logger.debug(f"extract error: {e}")
        return None

def build_get_link(domain: str, username: str, password: str):
    if not domain.startswith("http"):
        domain = "http://" + domain
    link = f"{domain}/get.php?username={username}&password={password}&type=m3u_plus"
    return link, domain

def create_ssl_connector(limit: int = 20):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ssl_ctx, limit=limit)

# ==================== فحص الحسابات ====================
async def check_account(session: aiohttp.ClientSession, domain: str, username: str, password: str):
    try:
        url = f"{domain}/player_api.php?username={username}&password={password}"
        async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=15, connect=8)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            user_info = data.get("user_info", {})
            status = str(user_info.get("status", "")).lower()
            if not (user_info and status in ["active", "enabled"]):
                return None
            
            exp = str(user_info.get("exp_date", "0"))
            exp_date = datetime.fromtimestamp(int(exp), tz=timezone.utc).strftime("%Y-%m-%d") if exp.isdigit() and exp != "0" else "غير معروف"
            
            return {
                "status": status.capitalize(),
                "exp_date": exp_date,
                "max_connections": user_info.get("max_connections", "غير معروف"),
            }
    except Exception as e:
        logger.debug(f"check error: {e}")
        return None

async def fetch_count(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=15, connect=8)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                return len(data) if isinstance(data, list) else 0
    except Exception:
        pass
    return 0

async def fetch_content_stats(session: aiohttp.ClientSession, domain: str, username: str, password: str):
    base = f"{domain}/player_api.php?username={username}&password={password}"
    live, vod, series = await asyncio.gather(
        fetch_count(session, f"{base}&action=get_live_streams"),
        fetch_count(session, f"{base}&action=get_vod_streams"),
        fetch_count(session, f"{base}&action=get_series"),
    )
    return {"📺 قنوات": live, "🎬 أفلام": vod, "🎞 مسلسلات": series}

# ==================== تنسيق الرسائل ====================
def format_success(n: int, domain: str, username: str, password: str, info: dict, link: str, stats: Optional[dict] = None, player_url: str = ""):
    stats_text = ""
    if stats:
        parts = "  |  ".join(f"{k}: {v:,}" for k, v in stats.items())
        stats_text = f"\n📦 المحتوى: {parts}"
    
    player_button = f"\n\n🎬 [فتح في المشغل]({player_url})" if player_url else ""
    
    return (
        f"📌 الحساب {n}\n\n"
        f"✅ الحساب يعمل بنجاح\n\n"
        f"🌐 الدومين: `{domain}`\n"
        f"👤 اليوزر: `{username}`\n"
        f"🔑 الباسورد: `{password}`\n"
        f"⏳ تاريخ الانتهاء: `{info['exp_date']}`\n"
        f"🔗 عدد الاتصالات: `{info['max_connections']}`\n"
        f"📊 الحالة: `{info['status']}`"
        f"{stats_text}\n"
        f"🔗 رابط الـGET:\n`{link}`"
        f"{player_button}"
    )

def format_summary(ok: int, bad: int, elapsed: float):
    total = ok + bad
    pct = round((ok / total) * 100) if total else 0
    return (
        f"📊 نتيجة الفحص\n"
        f"══════════════════\n"
        f"✅ الناجحة: {ok}\n"
        f"❌ الفاشلة: {bad}\n"
        f"📈 نسبة النجاح: {pct}%\n"
        f"⏱ الوقت: {elapsed:.1f} ثانية\n"
        f"══════════════════"
    )

def extract_urls(text: str):
    lines = text.splitlines()
    valid = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.search(r'https?://[^\s]+', line)
        if not match:
            continue
        url = match.group(0).replace("\\", "").replace('"', "").replace("'", "")
        if "get.php" in url and "username=" in url and "password=" in url:
            valid.append(url)
    return list(dict.fromkeys(valid))

# ==================== الكيبورد ====================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 الباقات", callback_data="btn_live")],
        [
            InlineKeyboardButton("🎬 أفلام", callback_data="btn_vod"),
            InlineKeyboardButton("🎞 مسلسلات", callback_data="btn_series"),
        ],
        [InlineKeyboardButton("📋 سجل الحسابات", callback_data="btn_history")],
        [InlineKeyboardButton("🎬 فتح المشغل", callback_data="btn_player")],
    ])

def build_paginated_keyboard(items: list, prefix: str, page: int = 1):
    total_pages = max(1, math.ceil(len(items) / ITEMS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * ITEMS_PER_PAGE
    page_items = items[start: start + ITEMS_PER_PAGE]

    keyboard = []
    for i, item in enumerate(page_items):
        item_name = str(item.get("name", item.get("category_name", "غير معروف")))[:50]
        keyboard.append([InlineKeyboardButton(item_name, callback_data=f"{prefix}_{start + i}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_pg_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_pg_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    back_map = {"items_live": "cats_live", "items_vod": "cats_vod", "items_series": "cats_series"}
    if prefix in back_map:
        keyboard.append([InlineKeyboardButton("🔙 رجوع للفئات", callback_data=back_map[prefix])])

    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="btn_main")])
    return InlineKeyboardMarkup(keyboard), page, total_pages

# ==================== معالجات الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # التحقق من الحظر
    user_data = db.get_user(user.id)
    if user_data and user_data.get("is_banned"):
        await update.message.reply_text("🚷 تم حظرك من استخدام البوت.")
        return
    
    # إضافة المستخدم
    is_new = db.add_user(user.id, user.username, user.first_name)
    
    # إشعار للأدمن (يمكنك تعديل ID الأدمن)
    admin_id = context.bot_data.get("admin_id")
    if is_new and admin_id:
        try:
            await context.bot.send_message(
                admin_id,
                f"🎉 *مستخدم جديد!*\n\n"
                f"👤 الاسم: {user.first_name}\n"
                f"🆔 ID: `{user.id}`\n"
                f"📱 المستخدم: @{user.username or 'لا يوجد'}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    
    await update.message.reply_text(
        "📡 *مرحباً بك في بوت فحص حسابات Xtream*\n\n"
        "📌 *طرق الإدخال:*\n"
        "1️⃣ رابط مباشر\n"
        "2️⃣ ثلاثة أسطر (دومين، يوزر، باسورد)\n"
        "3️⃣ ملف TXT\n\n"
        "📋 *الأوامر:*\n"
        "/history — سجل آخر الحسابات\n"
        "/stats — إحصائياتك الشخصية\n"
        "/player — فتح مشغل الويب",
        parse_mode="Markdown"
    )

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = db.get_user_history(update.effective_user.id)
    if not history:
        await update.message.reply_text("📋 السجل فارغ.")
        return
    
    lines = ["📋 *آخر الحسابات المفحوصة:*\n"]
    for i, h in enumerate(history, 1):
        lines.append(
            f"*{i}.* `{h['username']}` @ `{h['domain']}`\n"
            f"   ⏳ {h['exp_date']}  |  🕐 {h['checked_at']}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = db.get_user(update.effective_user.id) or {}
    total_checked = user_data.get("checks_count", 0)
    total_ok = user_data.get("ok_count", 0)
    total_bad = total_checked - total_ok
    pct = round((total_ok / total_checked) * 100) if total_checked else 0
    
    await update.message.reply_text(
        f"📊 *إحصائياتك*\n\n"
        f"🔍 إجمالي المفحوصة: *{total_checked}*\n"
        f"✅ الناجحة: *{total_ok}*\n"
        f"❌ الفاشلة: *{total_bad}*\n"
        f"📈 نسبة النجاح: *{pct}%*",
        parse_mode="Markdown"
    )

async def cmd_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إنشاء رابط للمشغل
    account = context.user_data.get("account", {})
    if account:
        stream_url = f"{account['domain']}/get.php?username={account['username']}&password={account['password']}&type=m3u_plus"
        player_url = f"https://your-koyeb-app.koyeb.app/player?url={stream_url}"
        await update.message.reply_text(
            f"🎬 *مشغل الويب*\n\n"
            f"[اضغط هنا للفتح]({player_url})\n\n"
            f"يدعم: HLS, M3U8, MP4",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🎬 *مشغل الويب*\n\n"
            "استخدم الرابط المباشر:\n"
            "`https://your-koyeb-app.koyeb.app/player?url=YOUR_STREAM_URL`",
            parse_mode="Markdown"
        )

# ==================== معالجة الروابط ====================
async def check_single(sem: asyncio.Semaphore, session: aiohttp.ClientSession, link: str, total: int, progress_msg, results: list):
    async with sem:
        data = extract_account_info(link)
        if not data:
            results.append(("bad", None, None, None, None, None))
        else:
            domain, username, password = data
            info = await check_account(session, domain, username, password)
            if info:
                stats = await fetch_content_stats(session, domain, username, password)
                results.append(("ok", domain, username, password, info, stats))
            else:
                results.append(("bad", None, None, None, None, None))

        done = len(results)
        ok_count = sum(1 for r in results if r[0] == "ok")
        filled = int(done / total * 10)
        bar = "█" * filled + "░" * (10 - filled)
        try:
            await progress_msg.edit_text(
                f"⏳ جاري الفحص...\n"
                f"{bar} {done}/{total}\n"
                f"✅ ناجح: {ok_count}  |  ❌ فاشل: {done - ok_count}"
            )
        except Exception:
            pass

async def process_links(links: list[str], update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not links:
        await update.message.reply_text("❌ ماكو روابط صالحة")
        return

    total = len(links)
    progress_msg = await update.message.reply_text(
        f"⏳ جاري الفحص...\n{'░' * 10} 0/{total}\n✅ ناجح: 0  |  ❌ فاشل: 0"
    )

    start_time = asyncio.get_event_loop().time()
    results = []

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    connector = create_ssl_connector(limit=MAX_CONCURRENT + 5)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            check_single(sem, session, link, total, progress_msg, results)
            for link in links
        ]
        await asyncio.gather(*tasks)

    elapsed = asyncio.get_event_loop().time() - start_time

    ok = 0
    bad = 0
    export_lines = []

    # رابط المشغل الأساسي
    base_url = "https://your-koyeb-app.koyeb.app"

    for status, domain, username, password, info, stats in results:
        if status == "ok":
            ok += 1
            get_link = f"{domain}/get.php?username={username}&password={password}&type=m3u_plus"
            
            # رابط مشغل الويب
            player_url = f"{base_url}/player?url={get_link}"
            
            msg = format_success(ok, domain, username, password, info, get_link, stats, player_url)

            context.user_data["account"] = {
                "domain": domain, "username": username, "password": password,
            }

            # حفظ في قاعدة البيانات
            db.add_history(update.effective_user.id, {
                "domain": domain, "username": username, "password": password,
                "exp_date": info["exp_date"], "status": info["status"]
            })
            db.log_check(update.effective_user.id, True)

            export_lines.append(get_link)
            await update.message.reply_text(msg, reply_markup=main_keyboard(), parse_mode="Markdown")
        else:
            bad += 1
            db.log_check(update.effective_user.id, False)

    await progress_msg.edit_text(format_summary(ok, bad, elapsed))

    if export_lines:
        file_content = "\n".join(export_lines).encode("utf-8")
        file_obj = io.BytesIO(file_content)
        file_obj.name = "valid_accounts.txt"
        await update.message.reply_document(
            document=file_obj,
            filename="valid_accounts.txt",
            caption=f"📁 الحسابات الناجحة ({ok} حساب)"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من الحظر
    user_data = db.get_user(update.effective_user.id)
    if user_data and user_data.get("is_banned"):
        await update.message.reply_text("🚷 تم حظرك من استخدام البوت.")
        return

    text = update.message.text.strip()
    links = extract_urls(text)
    if links:
        await process_links(links, update, context)
        return
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) == 3:
        domain, user, pwd = lines
        link, _ = build_get_link(domain, user, pwd)
        await process_links([link], update, context)
        return
    await update.message.reply_text("❌ بيانات غير صحيحة. أرسل رابطاً أو ثلاثة أسطر (دومين، يوزر، باسورد).")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        content = await file.download_as_bytearray()
        text = content.decode("utf-8", errors="ignore")
        links = extract_urls(text)
        if not links:
            await update.message.reply_text("❌ لم يتم العثور على روابط صالحة في الملف.")
            return
        await process_links(links, update, context)
    except Exception as e:
        logger.error(f"handle_document error: {e}")
        await update.message.reply_text("❌ تعذر قراءة الملف.")

# ==================== معالج الأزرار ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "noop":
        await query.answer()
        return

    try:
        await query.answer()
    except Exception:
        pass

    if data == "btn_history":
        history = db.get_user_history(update.effective_user.id)
        text = "📋 السجل فارغ." if not history else format_history(history)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="btn_main")]])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return

    if data == "btn_player":
        account = context.user_data.get("account", {})
        if account:
            stream_url = f"{account['domain']}/get.php?username={account['username']}&password={account['password']}&type=m3u_plus"
            player_url = f"https://your-koyeb-app.koyeb.app/player?url={stream_url}"
            await query.edit_message_text(
                f"🎬 *مشغل الويب*\n\n"
                f"[اضغط هنا للفتح]({player_url})\n\n"
                f"يدعم: HLS, M3U8, MP4",
                reply_markup=main_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await query.answer("❌ لا يوجد حساب نشط")
        return

    account = context.user_data.get("account", {})
    domain = account.get("domain", "")
    username = account.get("username", "")
    password = account.get("password", "")

    if not domain:
        try:
            await query.edit_message_text("❌ انتهت الجلسة. أرسل رابط جديد.")
        except Exception:
            pass
        return

    connector = create_ssl_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            # ... (نفس كود الأزرار السابق مع إضافة رابط المشغل للقنوات)
            if data == "btn_live":
                url = f"{domain}/player_api.php?username={username}&password={password}&action=get_live_categories"
                cats = await get_data(session, url)
                if not cats:
                    await query.edit_message_text("❌ لا توجد باقات")
                    return
                context.user_data["cats_live"] = cats
                keyboard, p, t = build_paginated_keyboard(cats, "cats_live")
                await query.edit_message_text(f"📺 الباقات (صفحة {p}/{t}):", reply_markup=keyboard)

            # ... (باقي الأزرار)

            elif data == "btn_main":
                info = await check_account(session, domain, username, password)
                if info:
                    link = f"{domain}/get.php?username={username}&password={password}&type=m3u_plus"
                    text = format_success(1, domain, username, password, info, link)
                else:
                    text = f"✅ الحساب\n🌐 `{domain}`"
                await query.edit_message_text(text, reply_markup=main_keyboard(), parse_mode="Markdown")

        except Exception as e:
            err = str(e)
            if "Message is not modified" not in err and "Query is too old" not in err:
                logger.error(f"button_handler error: {e}")

async def get_data(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=15, connect=8)) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.debug(f"get_data error: {e}")
    return []

async def get_stream_url(domain: str, username: str, password: str, item_id: str, stream_type: str = "live"):
    if stream_type == "live":
        return f"{domain}/live/{username}/{password}/{item_id}.m3u8"
    return f"{domain}/{stream_type}/{username}/{password}/{item_id}.mp4"

def format_history(history: list):
    lines = ["📋 *آخر الحسابات المفحوصة:*\n"]
    for i, h in enumerate(history, 1):
        lines.append(
            f"*{i}.* `{h['username']}` @ `{h['domain']}`\n"
            f"   ⏳ {h['exp_date']}  |  🕐 {h['checked_at']}\n"
        )
    return "\n".join(lines)
