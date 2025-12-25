import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.db import SessionLocal
from app.models import File, Share
from app.config import BASE_URL, DOWNLOAD_SECRET
from app.utils import sign_download_token

# =========================
# Config
# =========================
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])
PAGE_SIZE = 20
FILENAME_MAX = 26  # 文件名显示最大长度（超出截断）

# =========================
# Utils
# =========================
def is_admin(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == ADMIN_CHAT_ID

def db():
    return SessionLocal()

def fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"

def fit_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        name = "unnamed"
    if len(name) > FILENAME_MAX:
        return name[: FILENAME_MAX - 1] + "…"
    return name

def file_line(f: File) -> str:
    return f"ID {f.id} | {fit_name(f.filename)} | {fmt(f.created_at)}"

def signed_download_url(file_id: int, hours: int = 24) -> str:
    exp = int((datetime.utcnow() + timedelta(hours=hours)).timestamp())
    tok = sign_download_token(file_id, exp, DOWNLOAD_SECRET)
    return f"{BASE_URL}/d/{tok}"

def share_active(s: Share) -> bool:
    if s.revoked:
        return False
    if s.expires_at and s.expires_at <= datetime.utcnow():
        return False
    return True

def active_share(file: File) -> Share | None:
    now = datetime.utcnow()
    for s in file.shares:
        if (not s.revoked) and s.expires_at > now:
            return s
    return None

# =========================
# Keyboards
# =========================
def home_keyboard():
    # /start 首页：保持干净（你要求）
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 查看文件", callback_data="home:list")],
        [InlineKeyboardButton("🔍 按文件名搜索", callback_data="home:search_name")],
        [InlineKeyboardButton("🆔 按 ID 查询", callback_data="home:search_id")],
    ])

def list_type_keyboard():
    # “查看文件”二级页面：这里才出现返回（你要求）
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 文件", callback_data="list:document"),
         InlineKeyboardButton("🖼 图片", callback_data="list:photo")],
        [InlineKeyboardButton("🎬 视频", callback_data="list:video"),
         InlineKeyboardButton("🎵 音频", callback_data="list:audio")],
        [InlineKeyboardButton("🏠 返回主页", callback_data="nav:home")],
    ])

def back_home_only():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 返回主页", callback_data="nav:home")]
    ])

def collapsed_keyboard(f: File):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬇️ 操作", callback_data=f"open:{f.id}")],
        [InlineKeyboardButton("🏠 返回主页", callback_data="nav:home")],
    ])

def confirm_keyboard(action: str, fid: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认", callback_data=f"{action}_do:{fid}"),
            InlineKeyboardButton("❌ 取消", callback_data=f"open:{fid}")
        ],
        [InlineKeyboardButton("🏠 返回主页", callback_data="nav:home")],
    ])

def expanded_keyboard(f: File):
    rows = [
        [InlineKeyboardButton("⬇️ 下载（签名）", url=signed_download_url(f.id))]
    ]

    sh = active_share(f)
    if sh:
        rows.append([InlineKeyboardButton("🔗 分享链接", url=f"{BASE_URL}/s/{sh.token}")])
        rows.append([InlineKeyboardButton("❌ 取消分享", callback_data=f"revoke_confirm:{f.id}")])
    else:
        rows.append([InlineKeyboardButton("🔗 创建分享", callback_data=f"share_create:{f.id}")])

    rows.append([InlineKeyboardButton("🗑 删除文件", callback_data=f"delete_confirm:{f.id}")])
    rows.append([InlineKeyboardButton("⬆️ 收起", callback_data=f"close:{f.id}")])
    rows.append([InlineKeyboardButton("🏠 返回主页", callback_data="nav:home")])

    return InlineKeyboardMarkup(rows)

# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    context.user_data.clear()
    await update.message.reply_text(
        "📁 Telegram Drive 管理面板",
        reply_markup=home_keyboard()
    )

# =========================
# Callback
# =========================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(update):
        return

    s = db()
    try:
        data = q.data

        # ---- 返回主页（回到 /start 首页样式）----
        if data == "nav:home":
            context.user_data.clear()
            await q.message.edit_text(
                "📁 Telegram Drive 管理面板",
                reply_markup=home_keyboard()
            )
            return

        # ---- 首页：查看文件（二级页面）----
        if data == "home:list":
            context.user_data.clear()
            await q.message.edit_text(
                "📂 请选择要查看的类型",
                reply_markup=list_type_keyboard()
            )
            return

        # ---- 首页：搜索 ----
        if data == "home:search_name":
            context.user_data.clear()
            context.user_data["mode"] = "search_name"
            await q.message.reply_text("请输入文件名关键词：", reply_markup=back_home_only())
            return

        if data == "home:search_id":
            context.user_data.clear()
            context.user_data["mode"] = "search_id"
            await q.message.reply_text("请输入文件 ID：", reply_markup=back_home_only())
            return

        # ---- 二级页面：按类型列出 ----
        if data.startswith("list:"):
            ftype = data.split(":", 1)[1]
            files = (
                s.query(File)
                .filter(File.file_type == ftype)
                .order_by(File.id.asc())
                .all()
            )

            if not files:
                await q.message.reply_text("暂无该类型文件。", reply_markup=list_type_keyboard())
                return

            # 不清掉“类型选择”消息，让你可继续点别的类型/返回主页
            for f in files:
                await q.message.reply_text(
                    file_line(f),
                    reply_markup=collapsed_keyboard(f)
                )
            return

        # ---- 文件操作（展开/收起/分享/删除等）----
        if ":" not in data:
            return

        action, raw = data.split(":", 1)
        fid = int(raw)
        f = s.query(File).get(fid)
        if not f:
            return

        if action == "open":
            await q.message.edit_reply_markup(expanded_keyboard(f))
            return

        if action == "close":
            await q.message.edit_reply_markup(collapsed_keyboard(f))
            return

        if action == "share_create":
            share = Share(
                token=os.urandom(6).hex(),
                file_id=f.id,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                revoked=False
            )
            s.add(share)
            s.commit()
            await q.message.edit_reply_markup(expanded_keyboard(f))
            return

        if action == "revoke_confirm":
            await q.message.edit_reply_markup(confirm_keyboard("revoke", fid))
            return

        if action == "revoke_do":
            for sh in f.shares:
                sh.revoked = True
            s.commit()
            await q.message.edit_reply_markup(expanded_keyboard(f))
            return

        if action == "delete_confirm":
            await q.message.edit_reply_markup(confirm_keyboard("delete", fid))
            return

        if action == "delete_do":
            s.delete(f)
            s.commit()
            await q.message.edit_text("🗑 文件已删除", reply_markup=back_home_only())
            return

    finally:
        s.close()

# =========================
# Message handler（搜索输入）
# =========================
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message or not update.message.text:
        return

    mode = context.user_data.get("mode")
    if not mode:
        return

    s = db()
    try:
        text = update.message.text.strip()
        files = []

        if mode == "search_name":
            files = s.query(File).filter(File.filename.contains(text)).order_by(File.id.asc()).all()

        elif mode == "search_id":
            if text.isdigit():
                f = s.query(File).get(int(text))
                if f:
                    files = [f]
            else:
                await update.message.reply_text("请输入纯数字 ID。", reply_markup=back_home_only())
                return

        context.user_data.clear()

        if not files:
            await update.message.reply_text("未找到匹配文件。", reply_markup=back_home_only())
            return

        for f in files:
            await update.message.reply_text(
                file_line(f),
                reply_markup=collapsed_keyboard(f)
            )

    finally:
        s.close()

