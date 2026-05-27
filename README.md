# 财富 Alpha+ 个人开源版投研工作台

[![Version](https://img.shields.io/badge/version-0.1.5-blue.svg)](https://github.com/deancyl/alphaplus/releases/tag/v0.1.5)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-4fc08d.svg)](https://vuejs.org/)

像素级复刻专业投研工作台，基于 FastAPI + Vue3 + SQLite + AkShare 构建。

## 功能特性

### 核心模块 (19个功能视图)

| 模块 | 功能 | 数据来源 |
|------|------|----------|
| 首页宏观复盘 | 恐惧贪婪指数、ERP、风格强度、拥挤度 | AkShare |
| 基金筛选 | 5维度穿透筛选，26,801只基金，毫秒级响应 | AkShare |
| 基金对比 | 相关性热力矩阵，最多15只基金，实时Pearson计算 | 本地计算 |
| 相似度计算器 | 14因子暴露分析，SLSQP风格归因 | 本地计算 |
| 基金发行看板 | 新发基金周历管线 | AkShare |
| 基金公司透视 | Treemap资产分布 + 经理四象限气泡图 | AkShare |
| 股票行情 | A股实时行情 | AkShare |
| 债券行情 | 国债/信用债收益率曲线 | AkShare |
| 期货行情 | 商品/金融期货报价 | AkShare |
| 全球市场总览 | 8大全球指数、汇率、大宗商品 | AkShare |
| A股市场总览 | 7大A股指数、行业表现、北向资金 | AkShare |
| 债券市场总览 | 国债/国开债收益率曲线 | AkShare |
| 恐惧贪婪指数 | 半圆Gauge + 六维拓扑树 | 本地计算 |
| 市场风格强度 | 大小盘/成长价值风格切换 | AkShare |
| 股债ERP | SD/百分位双视角，±1SD/±2SD参考线 | AkShare |
| 市场拥挤度分析 | 相空间轨迹向量图，轮动动量可视化 | 本地计算 |
| **指数估值** | 17核心指数PE/PB百分位，历史曲线+markArea | AkShare |
| **定投计算器** | 周/双周/月定投收益计算，一次性对比 | 本地计算 |
| **指数专区** | 5类指数标签页，对比抽屉 | AkShare |

### 技术亮点

- **零数据成本**: 全部数据来自 AkShare 免费数据源
- **高性能查询**: 
  - SQLite WAL 模式 + 64MB 缓存
  - Pandas 内存筛选，26,801只基金 ~7ms 响应
- **量化引擎**:
  - 相空间轨迹计算 (位置、速度、加速度)
  - SciPy SLSQP 多因子暴露分析 (14因子)
  - 实时 Pearson 相关系数矩阵 (~4ms)
- **优雅降级架构**:
  - GBM 几何布朗运动模拟器 (价格/收益率)
  - O-U 均值回归模拟器 (恐惧贪婪/拥挤度)
  - 指数退避重试 + 令牌桶限流
- **高级可视化**:
  - ECharts markArea 估值区间着色
  - Sparkline 表格内嵌微图表
  - 相空间轨迹向量动画
- **移动端适配**: 响应式设计，支持手机/平板/电脑
- **实时刷新**: 30秒自动刷新行情数据

## 技术栈

**后端**: FastAPI + SQLite (WAL) + APScheduler + AkShare + Pandas + SciPy + Numba  
**前端**: Vue3 + TypeScript + Vite + ECharts + Element Plus + Tailwind CSS

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
│   │   └── fund.py       # 数据模型定义 (16张表)
│   ├── schemas/          # Pydantic 模式
│   ├── services/         # 业务逻辑
│   │   ├── akshare_data.py   # AkShare 数据服务
│   │   ├── pandas_cache.py   # Pandas 内存缓存
│   │   ├── quant_engine.py   # 量化计算引擎
│   │   ├── simulators.py     # GBM/O-U 随机模拟器
│   │   ├── correlation.py    # Pearson 相关性计算
│   │   ├── factor_exposure.py # SLSQP 因子暴露
│   │   ├── resilience.py     # 指数退避重试
│   │   ├── rate_limiter.py   # 令牌桶限流器
│   │   ├── cache.py      # 缓存服务
│   │   └── ingestion.py  # 数据导入服务
│   └── main.py           # 应用入口
├── frontend/              # Vue3 前端
│   ├── src/
│   │   ├── views/        # 16个页面组件
│   │   ├── components/   # 通用组件
│   │   │   ├── MegaMenu.vue      # 导航菜单 (支持移动端)
│   │   │   ├── SplitPanel.vue    # 弹性分栏组件
│   │   │   ├── IndexBar.vue      # 实时行情条
│   │   │   └── EChartsWrapper.vue # 图表封装 (markArea/sparkline/heatmap)
│   │   ├── api/          # API 服务层
│   │   ├── router/       # 路由配置
│   │   └── assets/styles/ # 全局样式
│   ├── tailwind.config.js # Tailwind 配置
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
| `/api/v1/fund/filter` | POST | 基金筛选 (支持5维度过滤，毫秒级响应) |
| `/api/v1/fund/{code}` | GET | 基金详情 |
| `/api/v1/fund/compare` | POST | 基金对比 (实时Pearson相关性矩阵) |
| `/api/v1/fund/issue` | GET | 基金发行日历 |
| `/api/v1/fund/company` | GET | 基金公司列表 |
| `/api/v1/fund/similarity/calc` | GET | 基金相似度计算 (因子暴露距离) |
| `/api/v1/fund/company/{id}/distribution` | GET | 公司资产配置分布 |

### 市场模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/market/indices` | GET | 核心指数行情 |
| `/api/v1/market/futures/quotes` | GET | 期货行情 |
| `/api/v1/market/global` | GET | 全球市场总览 |
| `/api/v1/market/domestic` | GET | A股市场总览 |
| `/api/v1/market/heatmap` | GET | 热力矩阵 |
| `/api/v1/market/dashboard` | GET | 首页看板聚合 (恐惧贪婪+ERP+风格+拥挤度) |

### 分析模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/analytics/fear-greed` | GET | 恐惧贪婪指数 |
| `/api/v1/analytics/erp` | GET | 股债ERP |
| `/api/v1/analytics/style-strength` | GET | 风格强度 |
| `/api/v1/analytics/crowding` | GET | 拥挤度分析 |
| `/api/v1/analytics/rotation-vector` | GET | 相空间轨迹向量 |
| `/api/v1/analytics/factor-exposure` | POST | 多因子暴露分析 (SLSQP) |

### 指数模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/market/index-valuation` | GET | 17核心指数PE/PB估值 |
| `/api/v1/market/index-valuation/{code}/history` | GET | 单指数PE历史数据 |
| `/api/v1/fund/aip-calculate` | POST | 定投收益计算 |

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

### v0.1.4 (2026-05-27)

**指数估值系统:**
- 17 个核心指数 PE/PB 数据 (沪深300, 中证500, 创业板指等)
- PE 百分位区间划分 (低估 0-25% / 正常 25-75% / 高估 75-100%)
- 历史 PE 曲线 + ECharts markArea 可视化
- 优雅降级: AkShare 失败时返回 GBM 模拟数据

**定投计算器:**
- 周/双周/月定投频率支持
- 总投入、当前价值、收益率、最大回撤计算
- 一次性投入对比分析
- NAV 曲线 + 投资日期标记

**指数专区:**
- 5 类指数标签页 (宽基/策略/增强/跨境/行业)
- 指数对比抽屉 (最多 5 个)
- 链接到估值详情页

**新增 API:**
- `GET /api/v1/market/index-valuation` 17 指数估值
- `GET /api/v1/market/index-valuation/{code}/history` PE 历史
- `POST /api/v1/fund/aip-calculate` 定投计算

**新增前端视图:**
- IndexValuation.vue - PE 仪表盘 + 历史图表
- FundCalcAIP.vue - 定投计算器表单 + 结果展示
- IndexZone.vue - 指数分类 + 对比功能

**测试覆盖:**
- test_index_valuation.py: 8 tests (估值数据/历史/性能)
- test_aip_calculator.py: 10 tests (计算/频率/验证)

**文件统计:**
- 17 files changed
- 2502+ insertions

### v0.1.5 (2026-05-27)

**V4.2 规范实现:**

**响应式基础设施:**
- useBreakpoint.ts: Vue 3 组合式 API 断点检测
- EChartsWrapper: ResizeObserver 内存泄漏修复 + 150ms 防抖
- 完全清理组件销毁时的资源

**移动端 UX 组件:**
- BottomSheet.vue: 触控友好底部抽屉
- 拖拽手势 + snap points (closed/half/full)
- WCAG 44px 触控目标最小尺寸
- 适配设计系统 CSS 变量

**量化特色指标:**
- new_high_ratio_1y: 近一年内含新高率 (招行特色)
- manager_honors: 基金经理荣誉 (金牛奖/明星基金奖/招行五星)

**风格可视化:**
- StyleBox.vue: 3x3 投资风格箱 (Morningstar 风格)
- 大盘/中盘/小盘 × 价值/混合/成长 九宫格
- 主导风格高亮显示

**新增 API 参数:**
- `new_high_ratio_min`: 基金筛选内含新高率阈值
- `manager_honors`: 基金详情返回经理荣誉

**新增前端组件:**
- frontend/src/composables/useBreakpoint.ts
- frontend/src/components/BottomSheet.vue
- frontend/src/components/StyleBox.vue
- frontend/src/services/fund_metrics.py

**测试覆盖:**
- test_new_high_ratio.py: 6 tests (schema + calculation)

**文件统计:**
- 12 files changed
- 1076+ insertions

### v0.1.3 (2026-05-26)

**基金池管理系统:**
- 三池架构: 准入池 (备选池) / 重点池 (核心池) / 出池 (已清退)
- 拖拽转移: 卡片拖拽实现池间转移
- 批量操作: 支持批量添加基金 (<200ms for 50 funds)
- 状态管理: 活跃/已移除状态跟踪

**我的自选管理:**
- localStorage 存储: 设备本地持久化，无需认证
- 混合模式: 支持可选后端同步 (`/api/v1/favorites`)
- 拖拽重排: 置顶/上移/下移操作
- 四类资产: 基金/股票/理财/保险分类管理
- Star 导航: Header 星标图标 + Badge 计数

**产品占位视图:**
- 理财筛选: "即将上线 - v0.2.0" 占位页
- 保险筛选: "即将上线 - v0.2.0" 占位页
- 存款产品: "即将上线 - v0.2.0" 占位页
- 黄金产品: "即将上线 - v0.2.0" 占位页

**新增 API:**
- `/api/v1/favorites` 自选 CRUD (GET/POST/DELETE/PUT)
- `/api/v1/pool` 基金池管理 (6 endpoints)
- `/api/v1/pool/transfer` 池间转移
- `/api/v1/pool/bulk-add` 批量添加

**新增数据库表:**
- `user_favorites_registry` 自选资产注册表
- `fund_pool_registry` 基金池状态明细表

**测试覆盖:**
- test_favorites.py: 6 tests (CRUD + reorder)
- test_pool.py: 6 tests (add/transfer/remove/status)

### v0.1.2 (2026-05-26)

**优雅降级架构:**
- GBM 几何布朗运动模拟器 (~10ms/1000路径)
- O-U 均值回归模拟器 (~16ms/1000路径)
- 指数退避重试装饰器 (5次重试, 2^n+jitter)
- 令牌桶限流器 (最大并发3)

**量化算法引擎:**
- Pearson 相关性矩阵 (~4ms/15基金)
- SLSQP 因子暴露分析 (~27ms, 14因子)
- 相空间轨迹计算 (位置/速度/加速度)

**API 增强:**
- `/api/v1/market/dashboard` 首页聚合端点
- `/api/v1/fund/similarity/calc` 相似度计算
- `/api/v1/fund/company/{id}/distribution` 资产配置

**前端降级 UI:**
- FundCompany: Treemap/气泡真实数据 + 模拟数据标识
- DomesticBondMarket: Sparkline真实渲染
- FundFilter: Sparkline NAV趋势API

**数据库模型:**
- MarketCalendar 多市场周历表
- FundNavHistory 导出修复

### v0.1.1 (2026-05-26)

**新功能:**
- Pandas 内存缓存服务，26,801只基金 ~7ms 筛选
- 相空间轨迹计算引擎，支持轮动动量可视化
- 实时 Pearson 相关系数矩阵，1小时缓存
- 7个前端视图增强 (SplitPanel, Treemap, 轨迹图等)
- Tailwind CSS 集成，PRD 语义色

**前端增强:**
- FundFilter: SplitPanel + sparkline + 300ms debounce
- FundCompare: 三角热力矩阵 + 拖拽重排 + 15只限制
- FundSimilarity: 14列因子暴露表 + 颜色编码
- FundCompany: Treemap资产分布 + 经理四象限图
- MarketCrowding: 相空间轨迹向量 + 动画控制
- FearGreed: 半圆Gauge + 六维拓扑树
- ERPSpread: SD/百分位切换 + ±1SD/±2SD线

**后端增强:**
- `pandas_cache.py`: GLOBAL_FUND_DF 单例缓存
- `quant_engine.py`: 相空间轨迹计算模块
- 基金对比相关系数缓存

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
- [Tailwind CSS](https://tailwindcss.com/) - 实用优先的 CSS 框架
- [Numba](https://numba.pydata.org/) - JIT 编译器
- [SciPy](https://scipy.org/) - 科学计算库
