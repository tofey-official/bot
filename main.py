import os
import logging
import threading
from flask import Flask
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import BOT_TOKEN, PORT, SECRET_KEY
from database import db
from admin_panel import admin_bp
from stream_player import player_bp
from bot_handlers import (
    start, cmd_history, cmd_stats, cmd_player,
    handle_text, handle_document, button_handler
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== Flask App ====================
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(player_bp, url_prefix='')

@app.route('/')
def home():
    return """
    <h1>🤖 Xtream Bot</h1>
    <p>البوت يعمل بنجاح!</p>
    <a href="/admin">لوحة التحكم</a> | 
    <a href="/player">مشغل الويب</a>
    """

# ==================== تشغيل البوت ====================
def run_bot():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(15)
        .pool_timeout(15)
        .build()
    )

    # تخزين admin_id للإشعارات (غيّر هذا الرقم)
    application.bot_data["admin_id"] = 123456789

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("player", cmd_player))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    logger.info("✅ Bot Running...")
    application.run_polling()

def run_web():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    # تشغيل البوت في thread منفصل
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # تشغيل الويب
    logger.info(f"🌐 Web server starting on port {PORT}")
    run_web()
