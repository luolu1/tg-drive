import io
from datetime import datetime

from telegram import Bot, InputFile, Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from app.config import BOT_TOKEN, CHANNEL_ID
from app.db import SessionLocal
from app.models import File as FileModel

from app.bot_admin import start as admin_start
from app.bot_admin import on_callback as admin_on_callback
from app.bot_admin import on_message as admin_on_message

bot = Bot(BOT_TOKEN)


def db():
    return SessionLocal()


def sha_placeholder(uid: str) -> str:
    return f"tguid:{uid}"


async def upload_to_channel(upload_file):
    await upload_file.seek(0)
    content = await upload_file.read()
    bio = io.BytesIO(content)
    bio.name = upload_file.filename

    msg = await bot.send_document(
        chat_id=CHANNEL_ID,
        document=InputFile(bio, filename=upload_file.filename),
        disable_notification=True
    )

    doc = msg.document
    tg_file = await bot.get_file(doc.file_id)

    return {
        "file_id": doc.file_id,
        "file_name": doc.file_name,
        "file_path": tg_file.file_path,
        "message_id": msg.message_id
    }


# =========================
# Channel listener
# =========================
async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg or msg.chat.id != CHANNEL_ID:
        return

    s = db()
    try:
        file_id = None
        file_unique_id = None
        filename = None
        file_type = None
        tg_file = None

        if msg.document:
            d = msg.document
            file_id = d.file_id
            file_unique_id = d.file_unique_id
            filename = d.file_name
            file_type = "document"
            tg_file = await context.bot.get_file(file_id)

        elif msg.photo:
            p = msg.photo[-1]
            file_id = p.file_id
            file_unique_id = p.file_unique_id
            filename = f"photo_{msg.message_id}.jpg"
            file_type = "photo"
            tg_file = await context.bot.get_file(file_id)

        elif msg.video:
            v = msg.video
            file_id = v.file_id
            file_unique_id = v.file_unique_id
            filename = v.file_name or f"video_{msg.message_id}.mp4"
            file_type = "video"
            tg_file = await context.bot.get_file(file_id)

        elif msg.audio:
            a = msg.audio
            file_id = a.file_id
            file_unique_id = a.file_unique_id
            filename = a.file_name or f"audio_{msg.message_id}.mp3"
            file_type = "audio"
            tg_file = await context.bot.get_file(file_id)

        else:
            return

        if s.query(FileModel).filter_by(tg_file_id=file_id).first():
            return

        rec = FileModel(
            filename=filename,
            file_type=file_type,
            sha256=sha_placeholder(file_unique_id),
            tg_file_id=file_id,
            tg_file_path=tg_file.file_path,
            tg_message_id=msg.message_id,
            created_at=datetime.utcnow(),
        )
        s.add(rec)
        s.commit()

    finally:
        s.close()


def build_bot_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", admin_start))
    app.add_handler(CallbackQueryHandler(admin_on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_on_message))

    app.add_handler(MessageHandler(filters.ALL, on_channel_post))

    return app

