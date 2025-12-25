from sqlalchemy import (
    Column, Integer, String, DateTime,
    ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)

    # 新增：文件类型（document / photo / video / audio）
    file_type = Column(String, nullable=False)

    sha256 = Column(String, unique=True, nullable=False)
    tg_file_id = Column(String, nullable=False)
    tg_file_path = Column(String, nullable=False)
    tg_message_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shares = relationship(
        "Share",
        back_populates="file",
        cascade="all, delete-orphan"
    )


class Share(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)

    file = relationship("File", back_populates="shares")

    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

