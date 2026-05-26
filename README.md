# 财富 Alpha+ 个人开源版投研工作台

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/deancyl/alphaplus/releases/tag/v0.1.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-4fc08d.svg)](https://vuejs.org/)

像素级复刻专业投研工作台，基于 FastAPI + Vue3 + SQLite + AkShare 构建。

## 功能特性

### 核心模块 (16个功能视图)

| 模块 | 功能 | 数据来源 |
|------|------|----------|
| 首页宏观复盘 | 恐惧贪婪指数、ERP、风格强度、拥挤度 | AkShare |
| 基金筛选 | 5维度穿透筛选，26,801只基金 | AkShare |
| 基金对比 | 相关性矩阵，最多15只基金 | 本地计算 |
| 相似度计算器 | 基金相似度分析 | 本地计算 |
| 基金发行看板 | 新发基金周历管线 | AkShare |
| 基金公司透视 | 215家基金公司总览 | AkShare |
| 股票行情 | A股实时行情 | AkShare |
| 债券行情 | 国债/信用债收益率曲线 | AkShare |
| 期货行情 | 商品/金融期货报价 | AkShare |
| 全球市场总览 | 8大全球指数、汇率、大宗商品 | AkShare |
| A股市场总览 | 7大A股指数、行业表现、北向资金 | AkShare |
| 债券市场总览 | 国债/国开债收益率曲线 | AkShare |
| 恐惧贪婪指数 | 7因子情绪指标 | 本地计算 |
| 市场风格强度 | 大小盘/成长价值风格切换 | AkShare |
| 股债ERP | 估值分位数分析 | AkShare |
| 市场拥挤度分析 | 资产拥挤度评分 | 本地计算 |

### 技术亮点

- **零数据成本**: 全部数据来自 AkShare 免费数据源
- **高性能查询**: SQLite WAL 模式，支持万级基金毫秒级筛选
- **移动端适配**: 响应式设计，支持手机/平板/电脑
- **实时刷新**: 30秒自动刷新行情数据

## 技术栈

**后端**: FastAPI + SQLite (WAL) + APScheduler + AkShare  
**前端**: Vue3 + TypeScript + Vite + ECharts + Element Plus

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

### 后端启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端 (默认端口 60200)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 60200
```

### 前端启动

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器 (默认端口 60201)
npm run dev
```

### 一键启动

```bash
./start.sh
```

## 项目结构

```
alphaplus/
├── backend/               # FastAPI 后端
│   ├── api/              # API 路由
│   │   ├── fund.py       # 基金相关 API
│   │   ├── market.py     # 市场行情 API
│   │   └── analytics.py  # 分析指标 API
│   ├── models/           # SQLAlchemy 模型
│   │   └── fund.py       # 数据模型定义
│   ├── schemas/          # Pydantic 模式
│   ├── services/         # 业务逻辑
│   │   ├── akshare_data.py  # AkShare 数据服务
│   │   ├── cache.py      # 缓存服务
│   │   └── ingestion.py  # 数据导入服务
│   └── main.py           # 应用入口
├── frontend/              # Vue3 前端
│   ├── src/
│   │   ├── views/        # 16个页面组件
│   │   ├── components/   # 通用组件
│   │   │   ├── MegaMenu.vue    # 导航菜单 (支持移动端)
│   │   │   ├── IndexBar.vue    # 实时行情条
│   │   │   └── EChartsWrapper.vue  # 图表封装
│   │   ├── api/          # API 服务层
│   │   ├── router/       # 路由配置
│   │   └── assets/styles/ # 全局样式
│   └── vite.config.ts    # Vite 配置
├── scripts/               # 工具脚本
│   ├── fetch_real_data.py # 数据导入脚本
│   └── seed_data.py      # 测试数据生成
└── requirements.txt       # Python 依赖
```

## API 文档

### 基金模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/fund/filter` | POST | 基金筛选 (支持5维度过滤) |
| `/api/v1/fund/{code}` | GET | 基金详情 |
| `/api/v1/fund/compare` | POST | 基金对比 (相关性矩阵) |
| `/api/v1/fund/issue` | GET | 基金发行日历 |
| `/api/v1/fund/company` | GET | 基金公司列表 |

### 市场模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/market/indices` | GET | 核心指数行情 |
| `/api/v1/market/futures/quotes` | GET | 期货行情 |
| `/api/v1/market/global` | GET | 全球市场总览 |
| `/api/v1/market/domestic` | GET | A股市场总览 |
| `/api/v1/market/heatmap` | GET | 热力矩阵 |

### 分析模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/analytics/fear-greed` | GET | 恐惧贪婪指数 |
| `/api/v1/analytics/erp` | GET | 股债ERP |
| `/api/v1/analytics/style-strength` | GET | 风格强度 |
| `/api/v1/analytics/crowding` | GET | 拥挤度分析 |

## 配置说明

### 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `CORS_ORIGINS` | `http://localhost:60201` | CORS 允许的源 (逗号分隔) |
| `DATABASE_PATH` | `data/alphaplus.db` | 数据库路径 |
| `SCHEDULER_ENABLED` | `false` | 是否启用定时任务 |

### 端口配置

- 后端: `60200`
- 前端: `60201`

## 数据说明

### 已导入数据

- **公募基金**: 26,801 只 (来自 AkShare fund_name_em)
- **基金公司**: 215 家 (来自 AkShare fund_aum_em)
- **恐惧贪婪指数**: 30 天历史数据
- **ERP 利差**: 100 天历史数据
- **风格强度**: 100 天历史数据
- **拥挤度分析**: 240 条记录

### 数据刷新

数据通过 AkShare 实时获取，部分数据支持定时刷新：
- 行情数据: 30秒自动刷新
- 基金数据: 每日 18:00 同步

## 版本历史

### v0.1.0 (2026-05-26)

**新功能:**
- 16 个功能视图全部实现
- 35+ API 端点
- 移动端响应式设计
- 汉堡菜单导航

**技术改进:**
- 消除所有技术债务
- 移除 mock 数据
- 替换 random 数据为真实 API
- CORS 配置可环境变量化
- AkShare 数据服务层

## 开发指南

### 添加新视图

1. 在 `frontend/src/views/` 创建 `.vue` 文件
2. 在 `frontend/src/router/index.ts` 添加路由
3. 在 `frontend/src/components/MegaMenu.vue` 添加菜单项

### 添加新 API

1. 在 `backend/models/fund.py` 添加数据模型
2. 在 `backend/schemas/fund.py` 添加 Pydantic 模式
3. 在 `backend/api/` 添加 API 路由
4. 在 `backend/main.py` 注册路由

## License

MIT

## 致谢

- [AkShare](https://github.com/akfamily/akshare) - 免费金融数据接口
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [ECharts](https://echarts.apache.org/) - 可视化图表库
- [Element Plus](https://element-plus.org/) - Vue 3 UI 组件库
