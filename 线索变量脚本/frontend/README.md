# 线索提效工具 - 前端项目

## 项目简介

本项目是线索提效工具的前端部分，使用 React + TypeScript + Vite 构建。提供文件上传、任务监控、结果展示等功能。

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **路由**: React Router DOM
- **HTTP 客户端**: Axios
- **UI 组件**: 自定义组件（基于 Tailwind CSS）
- **文件上传**: React Dropzone
- **图标**: Lucide React

## 开发环境要求

- Node.js >= 16
- npm >= 8

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000 查看应用。

### 3. 构建生产版本

```bash
npm run build
```

### 4. 预览生产版本

```bash
npm run preview
```

## 项目结构

```
frontend/
├── src/
│   ├── api/                # API 客户端
│   │   └── leadImportClient.ts
│   ├── components/         # 公共组件
│   │   ├── ui/            # 基础 UI 组件
│   │   ├── AppLayout.tsx  # 布局组件
│   │   ├── FileUploadCard.tsx
│   │   ├── ImportStatusCard.tsx
│   │   ├── ImportResultCard.tsx
│   │   ├── ImportLogsPanel.tsx
│   │   └── Sidebar.tsx
│   ├── hooks/             # 自定义 Hooks
│   │   └── useLeadImport.ts
│   ├── pages/             # 页面组件
│   │   └── LeadImportPage.tsx
│   ├── types/             # TypeScript 类型定义
│   │   └── leadImport.ts
│   ├── utils/             # 工具函数
│   │   ├── cn.ts
│   │   └── format.ts
│   ├── App.tsx            # 主应用组件
│   ├── main.tsx           # 应用入口
│   └── index.css          # 全局样式
├── public/                # 静态资源
├── package.json           # 项目配置
├── vite.config.ts        # Vite 配置
├── tailwind.config.js    # Tailwind CSS 配置
└── tsconfig.json         # TypeScript 配置
```

## 功能特性

### 核心功能
1. **文件上传**
   - 拖拽上传
   - 点击选择文件
   - 支持 xlsx/xls/csv 格式
   - 文件大小限制（10MB）

2. **任务监控**
   - 实时状态更新
   - 轮询机制
   - 进度展示

3. **结果展示**
   - 门店识别结果
   - 置信度显示
   - 文件下载
   - 处理日志

4. **状态管理**
   - 清晰的状态机设计
   - 错误处理
   - 重试机制

### 界面特性
- 响应式设计
- 企业级后台风格
- 清晰的视觉层次
- 友好的错误提示

## API 接口

### 开发环境
- 后端地址: http://127.0.0.1:18765
- Mock 模式: 可通过 `.env` 文件配置

### 主要接口
- `POST /api/leads/import` - 上传文件创建任务
- `GET /api/leads/import/jobs/{job_id}` - 查询任务状态
- `GET /api/leads/import/jobs/{job_id}/download` - 下载结果文件
- `GET /api/leads/import/stores` - 获取门店列表

## 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | http://127.0.0.1:18765 |
| `VITE_APP_ENV` | 应用环境 | development |
| `VITE_USE_MOCK` | 是否使用 Mock 数据 | false |

## 开发指南

### 添加新组件
1. 在 `src/components` 目录下创建组件
2. 使用 TypeScript 编写类型
3. 遵循现有的代码风格

### 修改 API
1. 更新 `src/types/leadImport.ts` 中的类型定义
2. 修改 `src/api/leadImportClient.ts`
3. 更新相关的组件

### 样式规范
- 使用 Tailwind CSS 类名
- 遵循 BEM 命名规范
- 保持组件样式隔离

## 部署

### 构建命令
```bash
npm run build
```

### 静态资源输出
构建后的文件将生成在 `dist/` 目录下。

## 注意事项

1. **API 契约**: 所有接口字段以 `docs/api-contract.md` 为准
2. **权限边界**: 只负责前端部分，不修改后端代码
3. **数据安全**: 所有客户数据必须使用脱敏样例
4. **状态管理**: 使用自定义 Hook 管理状态

## 故障排查

### 常见问题
1. **端口占用**: 修改 `vite.config.ts` 中的 port 配置
2. **API 连接失败**: 检查后端服务是否启动
3. **构建失败**: 检查 Node.js 版本和依赖安装

### 调试技巧
- 使用浏览器开发者工具
- 查看 Network 面板检查 API 调用
- 检查 Console 面板的错误信息

## 扩展功能

项目已预留以下扩展点：
- 自动外呼功能
- 数据看板
- 系统配置
- 门店脚本管理