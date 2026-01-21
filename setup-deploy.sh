#!/bin/bash
set -e

echo "正在使用 Docker Compose 启动全栈环境..."

# 编译并启动所有服务
# --build 确保代码更改后重新构建镜像
docker compose up -d --build

echo "------------------------------------------------"
echo "项目已在 Docker 中初始化并启动！"
echo "Django 运行在: http://localhost:8000"
echo "PureAdmin 运行在: http://localhost"
echo "可以使用 'docker compose logs -f web' 查看 Django 日志"
echo "可以使用 'docker compose logs -f celery' 查看 Worker 日志"
echo "可以使用 'docker compose logs -f frontend' 查看 前端日志 日志"
echo "------------------------------------------------"