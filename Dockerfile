# 使用稳定的官方 Python 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 环境变量（防止 pyc / 缓冲问题）
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 系统依赖（httpx / telegram 不需要额外依赖）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY app ./app

# 创建数据目录（真正的数据来自 volume）
RUN mkdir -p /data

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

