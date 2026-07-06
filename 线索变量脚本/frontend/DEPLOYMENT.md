# 部署指南

## 开发环境

### 1. 安装依赖
```bash
cd frontend
npm install
```

### 2. 启动开发服务器
```bash
# 正常模式
npm run dev

# Mock 模式（不依赖后端）
npm run dev:mock
```

访问 http://localhost:3000

### 3. 代码检查
```bash
# ESLint 检查
npm run lint

# 自动修复
npm run lint:fix

# TypeScript 类型检查
npm run type-check

# 格式化代码
npm run format
```

## 生产环境构建

### 1. 构建生产版本
```bash
# 正常模式
npm run build

# Mock 模式
npm run build:mock
```

### 2. 预览构建结果
```bash
npm run preview
```

### 3. 清理构建文件
```bash
npm run clean
```

## 环境变量配置

### 开发环境 (.env)
```
VITE_API_BASE_URL=http://127.0.0.1:18765
VITE_APP_ENV=development
VITE_USE_MOCK=false
```

### 生产环境 (.env.production)
```
VITE_API_BASE_URL=/api
VITE_APP_ENV=production
VITE_USE_MOCK=false
```

### Mock 模式 (.env.mock)
```
VITE_API_BASE_URL=/api
VITE_APP_ENV=development
VITE_USE_MOCK=true
```

## 部署到 Nginx

### 1. 构建项目
```bash
npm run build
```

### 2. Nginx 配置示例
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    # 处理前端路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api {
        proxy_pass http://backend-server:18765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态资源缓存
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. 部署命令
```bash
# 复制构建文件到服务器
scp -r dist/* user@server:/path/to/deploy/

# 重启 Nginx
ssh user@server "sudo nginx -s reload"
```

## Docker 部署

### 1. 创建 Dockerfile
```dockerfile
FROM node:18-alpine as builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 2. 构建 Docker 镜像
```bash
docker build -t lead-import-frontend .
```

### 3. 运行容器
```bash
docker run -d -p 80:80 lead-import-frontend
```

## 注意事项

1. **API 路径**：确保生产环境的 API 路径正确配置
2. **环境变量**：不同环境使用不同的配置文件
3. **CORS**：后端需要配置 CORS 以允许前端访问
4. **静态资源**：确保静态资源路径正确
5. **路由**：前端路由需要服务器支持 HTML5 History API