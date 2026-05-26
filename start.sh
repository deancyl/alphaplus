#!/bin/bash
# 财富 Alpha+ 启动脚本

cd /vol3/1000/docker/opencode/workspace/Alphaplus

echo "=========================================="
echo "  财富 Alpha+ 投研工作台"
echo "=========================================="
echo "  后端端口: 60200"
echo "  前端端口: 60201"
echo "  监听地址: 0.0.0.0"
echo "=========================================="
echo ""

# 清理旧进程
fuser -k 60200/tcp 2>/dev/null
fuser -k 60201/tcp 2>/dev/null
sleep 1

# 启动后端服务器
echo "正在启动后端服务器..."
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 60200 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

sleep 2

# 启动前端服务器
echo "正在启动前端服务器..."
cd frontend
nohup npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"
cd ..

sleep 2

echo ""
echo "=========================================="
echo "  服务已启动!"
echo "=========================================="
echo "  后端API:  http://localhost:60200/api/docs"
echo "  前端页面: http://localhost:60201"
echo "=========================================="
echo ""
echo "日志文件:"
echo "  后端: /tmp/backend.log"
echo "  前端: /tmp/frontend.log"
