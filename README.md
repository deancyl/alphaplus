# 财富 Alpha+ 个人开源版投研工作台

像素级复刻专业投研工作台，基于 FastAPI + Vue3 + SQLite + AkShare 构建。

## 技术栈

**后端**: FastAPI + SQLite (WAL) + APScheduler + AkShare  
**前端**: Vue3 + TypeScript + Vite + ECharts + Element Plus

## 快速开始

### 后端

```bash
cd backend
pip install -r ../requirements.txt
python main.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
alphaplus/
├── backend/           # FastAPI 后端
│   ├── api/          # API 路由
│   ├── models/       # SQLAlchemy 模型
│   ├── services/     # 业务逻辑
│   └── main.py       # 应用入口
├── frontend/          # Vue3 前端
│   ├── src/
│   │   ├── views/    # 页面组件
│   │   ├── components/ # 通用组件
│   │   ├── api/      # API 服务
│   │   └── stores/   # Pinia 状态
├── scripts/           # 工具脚本
└── requirements.txt   # Python 依赖
```

## 功能模块

1. 首页全局宏观复盘看板
2. 公募基金筛选沙盒
3. 公募基金对比沙盒
4. 相似度计算器
5. 公募基金发行看板
6. 公募基金公司透视
7. 行情资讯模块
8. 全市场总览
9. 国内债券市场总览
10. 恐惧贪婪指数
11. 市场风格强度
12. 股债收益差 (ERP)
13. 市场拥挤度分析

## License

MIT
