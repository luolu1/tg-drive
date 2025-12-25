# 📁 Telegram Drive（tg-drive）

**Telegram Drive** 是一个基于 **FastAPI + Telegram Bot** 构建的私有网盘系统。  
所有文件**直接存储在 Telegram 私有频道中**，服务器仅保存文件元数据，实现 **零服务器磁盘占用**。

---

## ✨ 功能特性

- 📦 文件直接存储在 **Telegram 私有频道**
- 🚫 **服务器不保存任何文件内容**（仅保存元数据）
- 🔐 支持 **签名下载链接**（防爬、防泄露）
- 👨‍💼 通过 **Telegram Bot** 进行管理
- 🌐 提供 **Web 管理后台**（FastAPI）
- 📂 按 Telegram 类型分类管理  
  - `document`：文件  
  - `photo`：图片  
  - `video`：视频  
  - `audio`：音频
- 🔗 支持创建 **可过期的分享链接**
- 🐳 完整 Docker 化，开箱即用
- 💾 SQLite 数据库通过 volume 持久化

---

## 🧱 系统架构

```text
用户 / Web 上传
        ↓
   Telegram Bot
        ↓
私有 Telegram 频道（真实文件存储）
        ↓
 FastAPI 服务（元数据 + 流式下载）
````

> Telegram 频道 = 文件存储层
> FastAPI = 管理与访问层

---

## 🚀 快速启动（Docker）

### 1️⃣ 准备 `.env` 文件

```env
BOT_TOKEN=你的机器人 Token
CHANNEL_ID=私有频道 ID
ADMIN_CHAT_ID=管理员 Telegram ID
API_TOKEN=Web 管理登录 Token
BASE_URL=http://你的服务器地址:8000
DOWNLOAD_SECRET=下载签名密钥
```

---

### 2️⃣ 启动容器

```bash
docker run -d \
  --name tg-drive \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/data \
  yourname/tg-drive:latest
```

---

### 3️⃣ 访问管理后台

浏览器访问：

```
http://localhost:8000/admin
```

---

## 🔧 环境变量说明

| 变量名               | 说明                 |
| ----------------- | ------------------ |
| `BOT_TOKEN`       | Telegram Bot Token |
| `CHANNEL_ID`      | 用于存储文件的私有频道 ID     |
| `ADMIN_CHAT_ID`   | 管理员 Telegram 用户 ID |
| `API_TOKEN`       | Web 管理后台登录口令       |
| `BASE_URL`        | 对外访问地址             |
| `DOWNLOAD_SECRET` | 下载链接签名密钥           |

---

## 💾 数据持久化说明

* SQLite 数据库存储路径：`/data/data.db`
* 通过 Docker volume 挂载实现持久化
* 容器删除 / 重建 **不会丢失数据**

---

## ⚠️ 使用注意事项

* Bot **必须是私有频道的管理员**
* 推荐仅用于 **个人或小团队私有使用**
* 默认使用 **Polling 模式**（无需公网 HTTPS）

---

## 📜 许可证

MIT License

---

## ⭐ 项目定位

这是一个：

> **利用 Telegram 作为“免费对象存储”的私有云网盘解决方案**

适合希望：

* 不占服务器磁盘
* 不依赖第三方对象存储
* 完全自托管
* 高度可控

的用户。

---

欢迎 Star / Fork / 自行部署 🚀

