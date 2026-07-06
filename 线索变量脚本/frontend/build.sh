#!/bin/bash

# 构建生产版本
echo "🔨 开始构建..."
npm run build

# 检查构建结果
if [ $? -eq 0 ]; then
    echo "✅ 构建成功！"
    echo "📦 构建文件位于 dist/ 目录"
    echo "👉 运行 'npm run preview' 预览生产版本"
else
    echo "❌ 构建失败！"
    exit 1
fi