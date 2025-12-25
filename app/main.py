import threading
import logging
import asyncio
import io
import urllib.parse
from datetime import datetime, timedelta
import httpx
import os

from fastapi import (
    FastAPI, UploadFile, File, Depends,
    Request, HTTPException, Form
)
from fastapi.responses import (
    StreamingResponse,
    JSONResponse,
    Response,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from telegram import Update

from app.db import init_db, SessionLocal
from app.models import File as FileModel, Share
from app.bot import upload_to_channel, build_bot_app
from app.config import BOT_TOKEN, API_TOKEN, BASE_URL, DOWNLOAD_SECRET
from app.utils import sha256_bytes, sign_download_token, verify_download_token
from app.auth import verify_api_or_cookie

# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s %(name)s] %(message)s"
)
logger = logging.getLogger("main")

# =========================
# FastAPI
# =========================
app = FastAPI(title="Telegram Drive")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

bot_thread: threading.Thread | None = None

# =========================
# Helpers
# =========================
def now_utc() -> datetime:
    return datetime.utcnow()

def content_disposition(filename: str) -> str:
    quoted = urllib.parse.quote(filename)
    return f'attachment; filename="download"; filename*=UTF-8\'\'{quoted}'

def is_full_url(v: str) -> bool:
    return v.startswith("http://") or v.startswith("https://")

def build_tg_download_url(path: str) -> str:
    path = (path or "").strip()
    if is_full_url(path):
        return path
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path.lstrip('/')}"

def share_active(share: Share) -> bool:
    if share.revoked:
        return False
    if share.expires_at and share.expires_at <= now_utc():
        return False
    return True

def make_signed_download_url(file_id: int, hours: int = 24) -> str:
    exp = int((now_utc() + timedelta(hours=hours)).timestamp())
    tok = sign_download_token(file_id, exp, DOWNLOAD_SECRET)
    return f"{BASE_URL}/d/{tok}"

# =========================
# Bot runner
# =========================
def run_bot_polling():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = build_bot_app()

    # 显式允许接收 channel_post，否则频道上传不会同步进 DB
    bot_app.run_polling(
        stop_signals=None,
        close_loop=False,
        allowed_updates=[
            "message",
            "callback_query",
            "channel_post",
            "edited_channel_post",
        ],
    )

# =========================
# Startup
# =========================
@app.on_event("startup")
def startup():
    global bot_thread
    init_db()
    bot_thread = threading.Thread(
        target=run_bot_polling,
        daemon=True
    )
    bot_thread.start()

# =========================
# DB
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================
# Web pages
# =========================
@app.get("/")
def root():
    return RedirectResponse("/admin")

@app.get("/admin/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/admin/login")
async def login_action(request: Request):
    form = await request.form()
    if form.get("token") != API_TOKEN:
        raise HTTPException(401)
    resp = RedirectResponse("/admin", 302)
    resp.set_cookie("api_token", API_TOKEN, httponly=True, samesite="lax")
    return resp

@app.get("/admin")
def admin_panel(
    request: Request,
    _: None = Depends(verify_api_or_cookie)
):
    return templates.TemplateResponse("drive.html", {"request": request})

# =========================
# API: file list（返回签名下载链接）
# =========================
@app.get("/api/files")
def api_files(
    q: str = "",
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_or_cookie)
):
    query = db.query(FileModel)
    if q:
        query = query.filter(FileModel.filename.contains(q))
    files = query.order_by(FileModel.id.desc()).all()

    result = []
    for f in files:
        shares = []
        for s in f.shares:
            shares.append({
                "id": s.id,
                "url": f"{BASE_URL}/s/{s.token}",
                "expires_at": s.expires_at.isoformat(),
                "revoked": s.revoked,
                "active": share_active(s),
            })
        result.append({
            "id": f.id,
            "filename": f.filename,
            "created_at": f.created_at.isoformat(),
            "download_url": make_signed_download_url(f.id, hours=24),
            "shares": shares,
        })
    return result

# =========================
# Upload（web 仍保留，可上传到频道）
# =========================
@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_or_cookie)
):
    data = await file.read()
    sha256 = sha256_bytes(data)

    # 上传到频道（不落地）
    new_file = UploadFile(filename=file.filename, file=io.BytesIO(data))
    result = await upload_to_channel(new_file)

    # 去重：tg_file_id
    exist = db.query(FileModel).filter_by(tg_file_id=result["file_id"]).first()
    if exist:
        return {"id": exist.id, "deduplicated": True}

    rec = FileModel(
        filename=result["file_name"],
        sha256=sha256,
        tg_file_id=result["file_id"],
        tg_file_path=result["file_path"],
        tg_message_id=result["message_id"],
        created_at=now_utc(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "deduplicated": False}

# =========================
# Share create / revoke（管理员鉴权）
# =========================
@app.post("/api/share")
def api_share_create(
    file_id: int = Form(...),
    expires_hours: int = Form(24),
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_or_cookie)
):
    file = db.query(FileModel).get(file_id)
    if not file:
        raise HTTPException(404)
    share = Share(
        token=os.urandom(6).hex(),
        file_id=file.id,
        expires_at=now_utc() + timedelta(hours=int(expires_hours)),
        revoked=False
    )
    db.add(share)
    db.commit()
    return {"url": f"{BASE_URL}/s/{share.token}"}

@app.post("/api/share/revoke")
def api_share_revoke(
    share_id: int = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_or_cookie)
):
    share = db.query(Share).get(share_id)
    if not share:
        raise HTTPException(404)
    share.revoked = True
    db.commit()
    return {"ok": True}

# =========================
# Delete file（管理员鉴权）
# =========================
@app.delete("/api/files/{file_id}")
def api_delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_or_cookie)
):
    f = db.query(FileModel).get(file_id)
    if not f:
        raise HTTPException(404)
    db.delete(f)
    db.commit()
    return {"ok": True}

# =========================
# Public Download: signed token
# =========================
@app.get("/d/{token}")
async def download_signed(token: str, request: Request, db: Session = Depends(get_db)):
    if not DOWNLOAD_SECRET:
        raise HTTPException(500, "DOWNLOAD_SECRET not configured")
    try:
        file_id, exp = verify_download_token(token, DOWNLOAD_SECRET)
    except Exception:
        raise HTTPException(404)
    if int(now_utc().timestamp()) > exp:
        raise HTTPException(404)
    f = db.query(FileModel).get(file_id)
    if not f:
        raise HTTPException(404)
    return await stream_telegram_file(f, request)

@app.head("/d/{token}")
def download_signed_head(token: str):
    return Response(status_code=200, headers={"Accept-Ranges": "bytes"})

# =========================
# Share Download
# =========================
@app.get("/s/{token}")
@app.head("/s/{token}")
async def download_share(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    share = db.query(Share).filter_by(token=token).first()
    if not share or not share_active(share):
        raise HTTPException(404)
    return await stream_telegram_file(share.file, request)

# =========================
# Core stream（支持 Range）
# =========================
async def stream_telegram_file(f: FileModel, request: Request):
    tg_url = build_tg_download_url(f.tg_file_path)
    range_header = request.headers.get("range")
    headers = {}
    if range_header:
        headers["Range"] = range_header

    async def gen():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", tg_url, headers=headers) as r:
                r.raise_for_status()
                async for c in r.aiter_bytes():
                    yield c

    return StreamingResponse(
        gen(),
        status_code=206 if range_header else 200,
        headers={
            "Content-Disposition": content_disposition(f.filename),
            "Accept-Ranges": "bytes",
        },
        media_type="application/octet-stream"
    )

# =========================
# Health
# =========================
@app.get("/api/ping")
def ping():
    return JSONResponse({"ok": True})

