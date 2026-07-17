# Module scope

本规则只覆盖 `线索变量脚本/frontend` 中的 React/TypeScript/Vite 线索导入原型。当前 AICC 工作台是仓库根目录的 `aicc-frontend-demo.html`；除非任务明确指定本目录，不要在此实现活动工作台功能。

# Source of truth

- `package.json`：开发、构建、测试、lint、格式化和类型检查命令。
- `package-lock.json`：npm 依赖锁定文件，安装时优先使用 `npm ci`。
- `vite.config.ts`：React 插件、`@` 路径别名、3000 开发端口及 `/api` 到 `127.0.0.1:18765` 的代理。
- `tsconfig.json`、`tsconfig.node.json`：严格 TypeScript 和 Vite 配置检查。
- `.eslintrc.json`：TypeScript、React Hooks 和 React Refresh 规则。
- `src/`：该原型的页面、组件、API 客户端、hooks 和类型定义。

# Setup and commands

从本目录运行：

~~~
npm ci
npm run dev
npm run build
npm run test
npm run lint
npm run type-check
~~~

开发服务器默认使用 3000 端口；需要真实 API 时先在 `glm-proxy` 启动 18765 后端。不要因为本目录存在 Vite 配置，就把根工作台改成需要 Node 构建的应用。

# Implementation rules

- 保持 React 18、TypeScript、Vite 和现有 `@/*` 路径别名；复用 `src` 中现有 API、类型和组件边界。
- API 请求使用 `/api` 相对路径，以便开发代理工作；不要在组件中复制后端基址。
- 改变 API 字段时同步更新客户端类型、调用方、错误状态和相关测试。
- `node_modules`、`dist`、coverage 和 Vite 缓存是生成内容，不手工编辑或提交。

# Validation

修改本原型后至少运行受影响测试、`npm run type-check` 和 `npm run lint`；交付前运行 `npm run build`。涉及真实 API 的交互还需同时启动 18765 后端并在浏览器中验证网络请求和控制台。
