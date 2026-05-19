import os
import re
import sqlite3
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application

# Setup Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "8696277622:AAGcAGxnTth-DVrwXAJv-Nj6ZB3YJei8W_Y"

# Sesuaikan path database agar permanen di direktori PythonAnywhere kamu
# Ganti 'vitopempek123' sesuai dengan username PythonAnywhere milikmu
USERNAME_PA = "vitopempek123" 
DB_FILE = f"/home/{USERNAME_PA}/database_catatan.db"

app = Flask(__name__)

# Inisialisasi Bot & Application secara global (tanpa start polling)
telegram_bot = Bot(token=TOKEN)
ptb_app = Application.builder().token(TOKEN).build()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catatan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            chat_id TEXT,
            message_id TEXT,
            topic_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Jalankan inisialisasi DB saat script dimuat
init_db()

async def proses_pesan(update: Update):
    """Logika utama untuk memproses pesan masuk via Webhook"""
    if not update.effective_message:
        return

    chat_id = str(update.effective_chat.id)
    message_id = str(update.effective_message.message_id)
    topic_id = str(update.effective_message.message_thread_id or "")

    # 1. JIKA ADA COMMAND /cari
    if update.effective_message.text and update.effective_message.text.startswith('/cari'):
        text = update.effective_message.text
        keyword = text.replace('/cari', '').strip()
        
        if not keyword:
            await telegram_bot.send_message(chat_id=chat_id, text="Gunakan format: `/cari kata_kunci`", message_thread_id=topic_id)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT text, chat_id, message_id FROM catatan WHERE text LIKE ?", (f"%{keyword}%",))
        rows = cursor.fetchall()
        conn.close()

        hasil = []
        for row in rows:
            db_text, db_chat_id, db_message_id = row
            clean_chat_id = db_chat_id.replace("-100", "")
            link = f"https://t.me/c/{clean_chat_id}/{db_message_id}"
            preview = db_text[:40] + "..." if len(db_text) > 40 else db_text
            hasil.append(f"• [{preview}]({link})")

        if hasil:
            respons = f"🔍 **Hasil pencarian untuk '{keyword}':**\n\n" + "\n".join(hasil)
        else:
            respons = f"❌ Tidak ditemukan catatan dengan kata kunci '{keyword}'."

        await telegram_bot.send_message(
            chat_id=chat_id,
            text=respons,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            message_thread_id=topic_id
        )
        return

    # 2. JIKA PESAN TEKS BIASA (BUKAN COMMAND) -> SIMPAN & AUTOFORMAT
    if update.effective_message.text:
        text = update.effective_message.text

        # Simpan ke SQLite
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO catatan (text, chat_id, message_id, topic_id) VALUES (?, ?, ?, ?)",
            (text, chat_id, message_id, topic_id)
        )
        conn.commit()
        conn.close()

        # Auto-Formatting (Code Block)
        sql_keywords = r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|FROM|WHERE|JOIN)\b"
        code_keywords = r"\b(def |function|import |if __name__)\b"
        
        if (re.search(sql_keywords, text, re.IGNORECASE) or re.search(code_keywords, text)) and "```" not in text:
            bahasa = "sql" if re.search(sql_keywords, text, re.IGNORECASE) else ""
            text_rapi = f"**💡 Format Otomatis (Code/Query):**\n\n```{bahasa}\n{text}\n```"
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=text_rapi,
                parse_mode="MarkdownV2",
                message_thread_id=topic_id
            )

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Endpoint URL Webhook yang akan dipanggil oleh Telegram"""
    if request.method == "POST":
        # Menggunakan event loop internal PTB untuk memproses update secara async
        update = Update.de_json(request.get_json(force=True), telegram_bot)
        ptb_app.create_task(proses_pesan(update))
        return "OK", 200
    return "Invalid", 400

@app.route('/', methods=['GET'])
def index():
    return "Bot Server is Running!", 200
