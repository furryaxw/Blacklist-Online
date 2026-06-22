<div align="center">

# 🛡️ Blacklist Online (Backend)

**一个现代化、高性能的黑名单管理系统后端。** 专为 OneBot 机器人生态设计，支持多端实时同步、审批流管理与精细化权限控制。

[特性](#-特性) • [安装](#-安装指南) • [配置](#-配置说明) • [API 文档](#-api-文档) • [许可证](#-license)

</div>

---

## 📖 简介

**Blacklist Online** 是一个基于 **FastAPI** 构建的异步后端服务，旨在解决分布式机器人集群中的黑名单同步与管理难题。

它不仅仅是一个简单的数据库 CRUD 封装，更包含了一套完整的 **Git-like 增量同步协议**，确保即使在网络不稳定的环境下，各个 Bot
节点也能高效、准确地同步最新的黑/白名单数据。同时，系统内置了完善的 RBAC 权限管理与审批工作流，适合社区协作治理。

## ✨ 特性

* **⚡ 高性能架构**: 基于 Python 3.10+ 和 FastAPI，全异步处理，支持高并发访问。
* **🔄 Git-like 增量同步**: 独创的同步协议 (`/sync`)，支持 `full_replace` 全量与 `incremental` 增量更新，大幅降低带宽消耗。
* **🛡️ 精细化权限控制 (RBAC)**: 内置 Owner, Super Admin, Admin, User 四级权限体系，支持 API Key 细粒度授权。
* **💾 双数据库隔离**: 采用 `System DB` (用户/配置) 与 `Blacklist DB` (业务数据) 分离设计，保障数据安全与迁移便利性。
* **🔌 OneBot 深度集成**: 原生支持 OneBot V11 协议，可实现验证码登录、消息通知与指令交互。
* **📡 WebSocket 实时控制台**: 提供全功能的 WebSocket 管理接口，支持前端实时监控、日志推送与远程会话管理。
* **📝 完善的审批流**: 支持用户申诉、黑名单添加/移除的申请与审批流程，自带证据留存字段。

## 🛠️ 技术栈

* **Web 框架**: [FastAPI](https://fastapi.tiangolo.com/)
* **ORM / 数据库**: SQLModel (SQLAlchemy + Pydantic) / SQLite (开启 WAL 模式)
* **数据库迁移**: Alembic
* **日志系统**: Loguru (支持自动轮转与保留策略)
* **验证与安全**: OAuth2 (Bearer Token), API Key, Rate Limiter (滑动窗口限流)

## 🚀 安装指南

### 环境要求

* Python 3.10 或更高版本
* Git

### 1. 克隆仓库

```bash
git clone https://github.com/furryaxw/Blacklist-Online.git
cd Blacklist-Online
git checkout backend

```

### 2. 创建虚拟环境 (推荐)

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate

```

### 3. 安装依赖

```bash
pip install -r requirements.txt

```

### 4. 初始化数据库

项目启动时会自动检查并创建数据库表结构（位于 `app/utils/database.py`）。如需执行高级迁移，请确保 `alembic` 已正确配置。

## ⚙️ 配置说明

在项目根目录下，将 `.env.example` 复制为 `.env` 并根据实际情况修改配置。

```ini
# --- 服务器配置 ---
PORT = 8000                 # 服务监听端口
HOST = 0.0.0.0              # 监听地址

# --- 数据库配置 (支持 SQLite/PostgreSQL) ---
# 系统库：存储用户、权限、日志
DATABASE_URL_SYSTEM = sqlite:///./data/system.db
# 业务库：存储黑名单、白名单、同步事件
DATABASE_URL_BLACKLIST = sqlite:///./data/blacklist.db

# --- OneBot 配置 ---
# 用于发送验证码、审核通知等
ONEBOT_API_URL = http://127.0.0.1:3000

```

## ▶️ 启动服务

### 开发模式

使用 `run.py` 入口直接启动，支持热重载：

```bash
python run.py

```

### 生产模式

建议使用 `uvicorn` 直接运行以获得更好性能：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

```

启动成功后，控制台将输出：

> 🚀 Server running on port 8000

## 📚 API 文档

服务启动后，访问以下地址查看交互式 API 文档：

* **Swagger UI**: `http://localhost:8000/docs`
* **ReDoc**: `http://localhost:8000/redoc`

### WebSocket 接口

WebSocket 入口位于 `/ws`。主要用于管理后台交互，消息格式如下：

```json
{
  "req_id": "uuid",
  "action": "auth.login",
  "data": {
    ...
  }
}

```

## 📂 项目结构

```text
.
├── app
│   ├── routers       # API 路由模块 (Auth, Bot, Sync, Admin等)
│   ├── utils         # 工具类 (数据库, 模型, 通知, Session管理)
│   ├── config.py     # 配置加载
│   └── main.py       # FastAPI 入口与生命周期管理
├── data              # 数据库文件存储目录 (自动生成)
├── logs              # 运行日志 (按日期轮转)
├── migrations        # Alembic 数据库迁移脚本
├── .env.example      # 环境变量示例
├── alembic.ini       # Alembic 配置文件
├── requirements.txt  # 项目依赖
└── run.py            # 启动脚本

```

## 🤝 贡献

欢迎提交 Issue 或 Pull Request！在提交代码前，请确保：

1. 代码可以通过静态检查。
2. 新增功能包含必要的数据库迁移脚本（如涉及模型修改）。

## 📄 License

本项目采用 [AGPL-3.0 License](LICENSE) 开源许可。