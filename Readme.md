<div align="center">

<img src="public/apple-touch-icon.png" alt="Shield Admin Logo" width="120" height="120" />

# 🛡️ Shield Admin

**Blacklist Online 的现代化管理控制台。**

基于 **WebSocket** 全双工通信，提供毫秒级的实时数据更新、审批流处理与可视化的数据看板。

[在线演示](https://www.furryaxw.top/Blacklist) · [功能特性](#-功能特性) · [快速开始](#-快速开始) · [部署指南](#-构建与部署)

</div>

---

## 📖 简介

**Shield Admin** 是 Blacklist Online 生态系统的官方前端实现。它打破了传统管理后台 "查改删+刷新" 的交互模式，采用全链路
WebSocket 通信。

这意味着当机器人（Bot）在群聊中提交举报，或者后台自动封禁某个用户时，您的管理面板无需刷新即可**实时弹出通知**并动态更新列表。配合
PWA 技术，它能像原生 App 一样安装在您的手机上，随时随地治理社区。

## ✨ 功能特性

* **⚡ 实时响应**: 基于 `NativeWsClient` 的 JSON-RPC 通信架构，告别轮询，所有状态变更实时同步。
* **📱 移动端**: 精心设计的响应式布局，在手机端自动切换为卡片式视图，操作体验媲美原生 App。
* **🎨 现代化 UI**: 深度集成的 **深色模式**，配合 Naive UI 的精致组件与 ECharts 数据可视化。
* **💾 PWA 支持**: 内置 Service Worker，支持添加到桌面、离线缓存静态资源，秒级首屏加载。
* **🛡️ 安全机制**: 集成 Browser Fingerprint（设备指纹）与 Token 分级存储策略（记住我/一次性会话）。
* **⚖️ 审批工作流**: 独创的 Diff 对比视图，直观展示黑名单变更前后的字段差异，辅助管理员快速决策。

## 🛠️ 技术栈

| 模块         | 技术选型                 | 说明                  |
|------------|----------------------|---------------------|
| **核心框架**   | Vue 3.3 + TypeScript | Script Setup 语法糖    |
| **构建工具**   | Vite 5+              | 极速冷启动与 HMR          |
| **UI 组件库** | Naive UI             | 高性能、可定制的主题系统        |
| **数据可视化**  | ECharts 5            | 动态交互式图表             |
| **通信协议**   | WebSocket (Native)   | 自研 JSON-RPC 封装与心跳保活 |
| **PWA**    | Vite PWA Plugin      | 离线访问与应用安装           |

## 🚀 快速开始

### 环境要求

* Node.js >= 16.0
* pnpm (推荐) 或 npm / yarn

### 1. 克隆项目

```bash
git clone https://github.com/furryaxw/Blacklist-Online.git
cd Blacklist-Online
git checkout frontend

```

### 2. 安装依赖

```bash
pnpm install
# 或者
npm install

```

### 3. 配置代理

开发环境下，前端需要连接到后端 API。编辑 `vite.config.ts` 中的 `proxy` 字段：

```typescript
// vite.config.ts
server: {
    proxy: {
        '/blacklist-api': {
            target: 'http://127.0.0.1:8000', // 指向您的后端地址
            changeOrigin: true,
            ws: true // 开启 WebSocket 代理
        }
    }
}
```

### 4. 启动开发服务器

```bash
npm run dev

```

访问 `http://localhost:8080`，您将看到登录页面。

## 📦 构建与部署

### 生产环境构建

```bash
npm run build

```

构建产物将输出至 `dist` 目录。该目录包含了自动生成的 `index.html`、Web Manifest 以及分包后的 JS/CSS 资源。

### Nginx 部署示例

由于项目是 SPA 且使用了 PWA，建议使用 Nginx 进行托管。以下是推荐配置：

```nginx
server {
    listen 80;
    server_name your-admin.com;
    root /path/to/blacklist-admin/dist;
    index index.html;

    # 1. 静态资源缓存策略
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # 2. SPA 路由重定向 (解决刷新 404)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 3. 反向代理后端 (API + WebSocket)
    location /blacklist-api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade; # 关键：支持 WebSocket
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}

```

## 📂 目录结构

```text
src
├── api             # 通信层 (WebSocket 封装)
├── assets          # 静态资源
├── components      # 公共组件 (QQUser, Modal等)
├── router          # 路由配置 (权限守卫)
├── store           # 状态管理 (User, Theme)
├── types           # TypeScript 类型定义
├── utils           # 工具库 (Date, Color, Fingerprint)
├── views           # 页面视图
│   ├── Dashboard.vue   # 控制台
│   ├── Blacklist.vue   # 黑名单列表
│   ├── Approvals.vue   # 审批流 (Diff视图)
│   └── Login.vue       # 登录 (指纹/验证码)
├── App.vue         # 根组件
└── main.ts         # 入口文件

```

## 🤝 参与贡献

我们非常欢迎社区贡献！如果您发现 Bug 或有新功能建议：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 License

本项目采用 [AGPL-3.0 License](LICENSE) 开源许可。