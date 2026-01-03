#!/bin/bash

# 设置报错即停止，确保流程安全
set -e

echo "开始初始化项目..."

# 1. 创建虚拟环境 (如果不存在)
if [ ! -d ".venv" ]; then
    echo "正在创建 Python 虚拟环境..."
    python3 -m venv .venv
    echo "虚拟环境创建成功。"
else
    echo "虚拟环境 .venv 已存在，跳过创建。"
fi

# 2. 激活虚拟环境
echo "正在激活虚拟环境..."
source .venv/bin/activate

# 3. 升级 pip 并安装依赖
echo "正在安装/更新依赖项 (requirements.txt)..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "警告: 未找到 requirements.txt，请确保依赖已手动安装。"
fi

# 4. 执行 Django 初始化脚本
echo "正在运行 Django 初始化指令..."
if [ -f "manage.py" ]; then
    # 这里会执行你之前编写的自定义命令
    python manage.py init_project
else
    echo "错误: 未找到 manage.py，请在项目根目录下运行此脚本。"
    exit 1
fi

echo "------------------------------------------------"
echo "项目初始化成功！"
echo "请运行 'source .venv/bin/activate' 启动开发环境。"
echo "------------------------------------------------"
