# 前端

React + Vite + Ant Design 管理前端，代码位于 `frontend/`。

## 命令

```bash
npm install
npm run dev
npm run build
npm run lint
```

开发服务器默认运行在 `http://localhost:5173`，`/api` 代理到 `http://127.0.0.1:8000`。

## 配置

- `VITE_DEV_PORT`：开发服务器端口，默认 `5173`。
- `VITE_API_TARGET`：`/api` 代理目标，默认 `http://127.0.0.1:8000`。

## 入口

页面和路由位于 `frontend/src/`。统一后端入口为 `knowledge/api/app_main.py`。