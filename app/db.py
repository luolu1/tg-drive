from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os   # ← 🔥 关键修复点

# 数据库存放路径（容器内）
DB_PATH = os.getenv("DB_PATH", "/data/data.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def init_db():
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)

