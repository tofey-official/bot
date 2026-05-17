import os
import json

# ==================== تكوين البوت ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ يرجى تعيين BOT_TOKEN في متغيرات البيئة")

# ==================== Firebase ====================
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS")
if FIREBASE_CREDENTIALS:
    # يقرأ JSON من متغير البيئة
    FIREBASE_CONFIG = json.loads(FIREBASE_CREDENTIALS)
else:
    FIREBASE_CONFIG = None

# ==================== إعدادات البوت ====================
ITEMS_PER_PAGE = 8
MAX_CONCURRENT = 10
REQUEST_TIMEOUT = 15
MAX_HISTORY = 10

# ==================== إعدادات لوحة التحكم ====================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # غيّرها!
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-here")

# ==================== Koyeb ====================
PORT = int(os.environ.get("PORT", 8080))
