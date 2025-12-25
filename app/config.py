import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
API_TOKEN = os.getenv("API_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# 新增：下载链接签名密钥（必须在 .env 配置）
DOWNLOAD_SECRET = os.getenv("DOWNLOAD_SECRET", "")
if not DOWNLOAD_SECRET:
    # 允许启动，但强烈建议配置，否则签名功能无法保证安全
    print("[WARN] DOWNLOAD_SECRET is empty. Signed download links will be insecure.")

