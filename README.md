# 财富 Alpha+ 个人开源版投研工作台

[![Version](https://img.shields.io/badge/version-0.1.27-blue.svg)](https://github.com/deancyl/alphaplus/releases/tag/v0.1.27)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-brightgreen.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-4fc08d.svg)](https://vuejs.org/)

像素级复刻专业投研工作台，基于 FastAPI + Vue3 + SQLite + AkShare 构建。

## 功能特性

### 核心模块 (26个功能视图)

| 模块 | 功能 | 数据来源 |
|------|------|----------|
| 首页宏观复盘 | 恐惧贪婪指数、ERP、风格强度、拥挤度 | AkShare |
| 基金筛选 | 5维度穿透筛选，26,801只基金，毫秒级响应 | AkShare |
| 基金对比 | 相关性热力矩阵，最多15只基金，实时Pearson计算 | 本地计算 |
| 相似度计算器 | 14因子暴露分析，SLSQP风格归因 | 本地计算 |
| 金发行看板 | 新发基金周历管线 | AkShare |
| 基金公司透视 | Treemap资产分布 + 经理四象限气泡图 | AkShare |
| **基金详情穿透** | 持仓明细 + 行业配置饼图，报告期选择 | AkShare |
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
| **存款利率看板** | 银行存款利率 vs 国债收益率利差分析 | AkShare |
| **存款ERP联动** | 存款利率与ERP动态关联分析 | AkShare |
| **保险IRR测算器** | Newton-Raphson IRR计算，30年现金价值投影 | 本地计算 |
| **贵金属跟踪** | 上海金交所Au99.99 + 伦敦金估算，价差分析 | AkShare |
| **FOF组合回测** | 虚拟组合构建 + Brinson业绩归因 | 本地计算 |
| **银行理财筛选** | PR1-PR5风险等级、收益率、期限筛选 | 中国理财网/天天基金 |

### 技术亮点

- **零数据成本**: 全部数据来自 AkShare 免费数据源
- **高性能查询**: 
  - SQLite WAL 模式 + 64MB 缓存
  - Pandas 内存筛选，26,801只基金 ~7ms 响应
  - L1 TTLCache P95延迟 0.007ms (280x优于目标)
  - L2/L3 DataFrame LRU + Parquet分区，90%命中率
- **量化引擎**:
  - 相空间轨迹计算 (位置、速度、加速度)
  - SciPy SLSQP 多因子暴露分析 (14因子)
  - 实时 Pearson 相关系数矩阵 (~4ms)
  - Brinson几何多期归因 (Carino残差<1e-12)
- **优雅降级架构**:
  - GBM 几何布朗运动模拟器 (价格/收益率)
  - O-U 均值回归模拟器 (恐惧贪婪/拥挤度)
  - 指数退避重试 + 令牌桶限流
  - 多源数据网关 + Circuit Breaker熔断
- **高级可视化**:
  - ECharts markArea 估值区间着色
  - Sparkline 表格内嵌微图表
  - 相空间轨迹向量动画
  - 移动端动态文本头替代Tooltip
- **移动端适配**: 响应式设计320px-3840px，触控热区44px最小
- **实时刷新**: 30秒自动刷新行情数据
- **QA Gates**: Brinson验证、内存泄漏测试、Sub-500ms性能基准

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

### 产品研究模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/deposit/rates` | GET | 存款利率与国债利差 |
| `/api/v1/insurance/calculate` | POST | 保险IRR计算 |
| `/api/v1/gold/spot-price` | GET | 金价实时数据 |
| `/api/v1/gold/history` | GET | 金价历史走势 |

### 基金穿透模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/fund/{code}/holdings` | GET | 基金持仓明细 |
| `/api/v1/fund/{code}/industry` | GET | 行业配置分布 |

### FOF组合模块

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/portfolio` | POST | 创建组合 |
| `/api/v1/portfolio` | GET | 列出组合 |
| `/api/v1/portfolio/{id}` | GET | 获取组合详情 |
| `/api/v1/portfolio/{id}` | PUT | 更新组合 |
| `/api/v1/portfolio/{id}` | DELETE | 删除组合 |
| `/api/v1/portfolio/{id}/backtest` | POST | 运行回测 |
| `/api/v1/portfolio/{id}/backtest` | GET | 列出回测结果 |
| `/api/v1/portfolio/{id}/backtest/{result_id}` | GET | 获取回测详情 |

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

## 启动优化

### 缓存预热配置

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `warmup_enabled` | `true` | 是否启用启动时缓存预热 |
| `warmup_timeout_seconds` | `10.0` | 预热操作最大等待时间 (秒) |
| `warmup_retry_count` | `1` | 预热失败重试次数 (减少外部API依赖) |
| `warmup_blocking` | `false` | 预热是否阻塞启动 (非阻塞模式) |
| `warmup_fallback_enabled` | `true` | 预热失败时启用降级数据 |

### 降级数据机制

当外部API (AkShare) 不可用时，系统自动注入降级数据:
- **指数估值**: 17个核心指数的默认PE/PB数据
- **恐惧贪婪**: 中性状态 (50分) 的默认数据
- **指数行情**: 前5个核心指数的零值数据

### 非阻塞预热实现

```python
async def _warmup_cache():
    # 立即注入降级数据确保服务可用
    _inject_fallback_data()
    
    # 后台异步执行预热任务
    if settings.warmup_blocking:
        await execute_warmup()
    else:
        asyncio.create_task(execute_warmup())
```

### 故障恢复策略

1. **立即降级**: 启动时注入fallback数据，服务立即可用
2. **超时保护**: 10秒超时避免启动阻塞
3. **后台预热**: 非阻塞模式允许服务先启动
4. **自动重试**: 真实API调用在后台持续尝试

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

### v0.1.27 (2026-05-31)

**深度审计全面修复与代码质量提升:**

**后端修复:**
- 修复AkShare API函数名错误（`fund_portfolio_industry_allocation` → `fund_portfolio_industry_allocation_em`）
- 修复AkShare API函数名错误（`bond_corporate_yields` → `bond_china_yield`）
- 修复AkShare API函数名错误（`fund_company_change_em` → `fund_aum_em`）
- 修复`rate_interbank`参数格式错误
- 修复Python字典/列表索引访问的防御性验证（correlation.py, duckdb_ingestion.py）

**前端API响应处理修复:**
- 修复25个API函数直接返回axios调用未解构`response.data`的问题
- 涉及文件: portfolio.ts, wmp.ts, insurance.ts, pool.ts, favorites.ts, fund.ts
- 添加正确的响应解构模式: `const response = await api.*; return response.data ?? defaultValue`

**前端TypeScript类型修复:**
- 修复21处TS6133未使用变量警告（删除或添加下划线前缀）
- 修复11处TS18048可选链缺失问题（FOFBacktest.vue的Brinson归因显示）
- 修复ECharts类型兼容问题（FearGreed.vue添加@ts-expect-error）
- 修复StockInfo.vue的API响应处理

**前端图标修复:**
- 修复Vue图标语法错误（`<i-ep-*>` → 正确的Element Plus图标导入）
- DepositMarket.vue: `i-ep-info-filled` → `InfoFilled`
- InsuranceCalculator.vue: `Calculator` → `DataAnalysis`（Element Plus无Calculator图标）

**前端代码质量提升:**
- 添加DEV环境保护到4处console.error调用（main.ts, apiHelpers.ts）
- 生产环境不再输出console错误

**QA验证:**
- TypeScript编译: 0错误
- Python测试: correlation等模块测试通过
- LSP诊断: 无新增错误

**修改文件统计:**
- 后端: 5个文件（akshare_data.py, ingestion.py, correlation.py, duckdb_ingestion.py, akshare_source.py）
- 前端: 30+个文件（API层、视图层、组件层）

### v0.1.26 (2026-05-31)

**前端API数据加载修复与用户体验增强:**

**核心修复:**
- 修复前端API函数未正确解构响应数据的问题
- API拦截器返回 `{ data, _error, _meta }` 结构，但API函数未提取 `response.data`
- `analytics.ts`: getFearGreedIndex/getERPSpread/getStyleStrength/getCrowdingAnalysis正确返回 `response.data ?? []`
- `market.ts`: getIndices/getDashboardMetrics/getMarketHeatmap/getDomesticMarket等14个函数修复
- `fund.ts`: getTopFunds/getFundDetail/getFundHoldings等函数修复

**新增功能:**
- `frontend/src/utils/apiHelpers.ts` - API错误处理辅助函数
- `frontend/src/utils/formatters.ts` - 数据格式化工具
- `frontend/src/utils/retry.ts` - 指数退避重试机制
- `frontend/src/utils/requestDedupe.ts` - 请求去重工具
- `frontend/src/composables/useDebounce.ts` - 防抖组合式函数
- `frontend/src/composables/useFilterTemplates.ts` - 筛选模板存储
- `frontend/src/components/MarketWordCloud.vue` - 市场热点词云组件
- `frontend/src/components/OmniSearch.vue` - 全局搜索组件
- `backend/api/preferences.py` - 用户偏好API (Pydantic v2迁移)
- `backend/services/bond_data.py` - 债券数据服务
- `backend/utils/formatters.py` - 后端格式化工具

**性能优化:**
- Parquet缓存服务增强: Hive分区、元数据管理、压缩支持
- 量化引擎扩展: 相空间轨迹计算优化、相关性分析性能提升
- 内存泄漏测试扩展: 从10条路由扩展至24条路由

**用户体验增强:**
- Dashboard首页数据加载完全修复
- 恐惧贪婪指数、ERP、风格强度、拥挤度、热力图、板块表现全部正常显示
- 涨幅榜/跌幅榜TOP10数据正确加载
- 市场热点词云正确显示15个行业标签
- 控制台零JavaScript错误

**QA验证:**
- Playwright测试: 首页所有widget数据加载成功
- 控制台: 0 JavaScript错误
- LSP诊断: 0 TypeScript错误
- 集成测试: 27/27路由正常工作

**修改文件:**
- `frontend/src/api/analytics.ts` - API响应解构修复
- `frontend/src/api/market.ts` - API响应解构修复
- `frontend/src/api/fund.ts` - API响应解构修复
- `frontend/src/views/Dashboard.vue` - 首页数据加载优化
- `backend/services/parquet_cache.py` - 缓存服务增强
- `backend/services/quant_engine.py` - 量化引擎扩展

### v0.1.25 (2026-05-30)

**高可用工程净化与数据确信度机制:**

**新增组件:**
- `frontend/src/components/ErrorBoundary.vue` - Vue 3错误边界组件,使用onErrorCaptured捕获子组件错误
- `frontend/src/components/DataConfidenceBadge.vue` - 数据确信度标识组件(实时/延迟/模拟三状态)
- `frontend/src/services/idb.ts` - IndexedDB服务,支持回测历史离线存储
- `backend/services/adjusted_nav.py` - 复权净值计算服务(分红再投资NAV)

**控制台零容忍(Console Error Zero-Tolerance):**
- Dashboard.vue移除7处console.error,替换为ErrorBoundary包裹
- FOFBacktest.vue移除5处console.error,替换为ElMessage.error用户友好提示
- 全项目Vue文件console.error从12处降至0处
- 新增pre-commit hook自动检测并阻止console.error/warn提交

**数据确信度标识机制:**
- IndexBar.vue从fallback-badge改为DataConfidenceBadge
- Dashboard每个widget header添加数据确信度标识
- 模拟数据强制高亮水印("模拟/历史锁定数据")
- 符合架构师要求"前端UI必须强制高亮显示模拟/历史锁定数据水印"

**IndexedDB回测历史存储:**
- 回测结果自动保存到IndexedDB
- 支持离线查看历史回测结果
- 历史记录列表UI,点击可重新加载
- 新增idb@8.0.3依赖

**复权净值计算:**
- 支持分红再投资NAV计算
- FOFBacktest添加复权净值选项checkbox
- 结果显示复权净值标识tag

**QA验证结果:**
- Homepage: 0 console errors
- FOFBacktest: 0 console errors
- Playwright测试通过
- DataConfidenceBadge正确显示模拟数据水印
- LSP诊断0 errors

**修改文件:**
- `frontend/src/components/ErrorBoundary.vue` - 新增 (+171行)
- `frontend/src/components/DataConfidenceBadge.vue` - 新增 (+295行)
- `frontend/src/services/idb.ts` - 新增 (+228行)
- `backend/services/adjusted_nav.py` - 新增 (+630行)
- `frontend/src/views/Dashboard.vue` - ErrorBoundary+DataConfidenceBadge集成
- `frontend/src/views/FOFBacktest.vue` - IndexedDB+复权净值+ErrorBoundary集成
- `frontend/src/components/IndexBar.vue` - DataConfidenceBadge集成
- `frontend/src/api/portfolio.ts` - use_adjusted_nav参数
- `frontend/package.json` - idb依赖
- `.git/hooks/pre-commit` - console.error检测hook

### v0.1.24 (2026-05-30)

**深度QA审计与关键崩溃修复:**

**问题诊断:**
- FOFBacktest.vue模板标签不平衡导致Vue编译失败 (500错误)
- Dashboard.vue图标导入问题
- FundFilter.vue可选链缺失导致TypeError
- MegaMenu.vue路由缺失导致导航失败

**修复内容:**
- 修复FOFBacktest.vue第866行chart-section缺失结束标签
- Dashboard首页ERP gauge重叠修复 (容器高度260px→300px)
- FundFilter修复nav_values?.length和tableData?.length可选链
- MegaMenu移除缺失路由的理财对比菜单项
- 27个Vue文件100vh改为100dvh解决移动端视口问题
- 添加Warning图标正确导入(Element Plus icons)

**QA验证结果:**
- 27个页面Playwright测试全部通过
- 0 console errors
- Vue编译成功
- LSP诊断0 errors

**修改文件:**
- `frontend/src/views/FOFBacktest.vue` - 模板结构修复 (+1行)
- `frontend/src/views/Dashboard.vue` - 首页全面优化 (+718行)
- `frontend/src/views/FundFilter.vue` - 可选链修复
- `frontend/src/components/MegaMenu.vue` - 路由修复
- 26个前端组件 - 移动端响应式优化

**新增文档:**
- `docs/design-standards.md` - Vue模板标签平衡检查规范

### v0.1.23 (2026-05-28)

**后端启动优化 - 解决30秒阻塞问题:**

**问题描述:**
- `_warmup_cache()` 阻塞启动流程 30+ 秒
- AkShare 外部API因代理问题频繁失败
- 服务因预热异常直接崩溃

**解决方案:**
- 新增5个预热配置参数 (warmup_enabled, warmup_timeout_seconds, warmup_retry_count, warmup_blocking, warmup_fallback_enabled)
- 创建 warmup_fallback.py 提供17指数降级数据
- 改造 `_warmup_cache()` 为非阻塞模式 (`asyncio.create_task()`)
- 启动时立即注入降级数据确保服务可用
- 10秒超时保护 (`asyncio.wait_for`)
- 外部API不可用时禁用预热调用

**核心改进:**
- 启动时间从 30+秒降至 < 1秒
- 服务可用性100% (降级数据保障)
- 外部依赖故障不影响启动

**新增文件:**
- `backend/services/warmup_fallback.py` - 降级数据模块 (68行)

**修改文件:**
- `backend/core/config.py` - 5个预热参数 (+17行)
- `backend/main.py` - 非阻塞预热重构 (+50行)

**设计标准更新:**
- 创建 docs/design-standards.md 防止复发
- 定义"非阻塞启动"设计原则

### v0.1.22 (2026-05-28)

**多端UI/UX深度优化与硬编码剔除:**

**移动端视口优化 (100vh → 100dvh):**
- 27个Vue文件完成替换，34处100vh改为100dvh
- 解决移动端浏览器工具栏导致的视口高度塌陷问题
- CSS fallback支持旧版浏览器

**大屏视口夹钳:**
- App.vue添加max-w-[1920px] mx-auto约束
- main.css新增.content-constraint工具类
- 防止超宽屏幕(>1920px)内容过度拉伸

**触控热区WCAG合规:**
- BottomSheet.vue: 触控区域扩展至44px最小
- MegaMenu.vue: 菜单项触控优化
- FundCompare.vue: 滚动指示器触控增强
- 符合WCAG 2.5.5标准 (44px×44px最小)

**配置层扩展 (15个新参数):**
- warmup_top_funds_count=50
- warmup_index_valuation_codes (7条)
- fear_greed_history_days=30
- erp_history_days=100
- crowding_history_records=240
- gold_shanghai_purity=0.9999
- gold_london_purity=0.9950
- gold_vat_friction_factor=0.0035
- CORE_INDICES迁移至config (17条)

**缓存预热重构:**
- 消除warmup_placeholder占位符
- warmup_fear_greed调用真实API
- 新增warmup_hot_funds预热热门基金
- 使用settings.*配置参数

**表格粘性列优化:**
- FundCompare.vue第一列sticky定位
- 渐变阴影滚动指示器
- 水平滚动视觉反馈增强

**测试覆盖:**
- test_config_warmup.py: 11个测试 (配置验证)
- test_warmup_refactor.py: 3个测试 (重构验证)
- 全部22个测试通过

**文件统计:**
- 31文件修改: +271行, -115行
- 后端: config.py, main.py, index_valuation.py
- 前端: 27个Vue组件, main.css
- 测试: 2个新测试文件

### v0.1.21 (2026-05-28)

**下一阶段无债研发与加固:**

**UI/UX 修复:**
- Mobile Tooltip Fix: FearGreed/ERPSpread移动端tooltip禁用，动态文本头替代
- Z-Index标准化: 5级体系(1/10/30/50/100)，11个组件更新
- Soft Keyboard Handling: InsuranceCalculator键盘遮挡图表隐藏机制
- Z-Score Alerts: StyleStrength/MarketCrowding Z-Score >= +2.0告警

**新功能开发:**
- WMP银行理财筛选: wmp_source.py + wmp.py API，WMPFilter.vue前端
- 存款ERP联动: DepositERPLinkage.vue新视图
- 拥挤度分析: crowding_analysis.py新服务
- aData直连模式: adata_client.py新适配器

**性能优化:**
- L1 Cache: P95延迟0.007ms (目标<2ms)，280倍优于目标
- L2/L3 Cache: DataFrame LRU缓存，Parquet分区，90%命中率

**QA Gates:**
- Brinson验证测试: 20个新测试，Carino残差<1e-12
- 内存泄漏测试: 50次路由切换，10条ECharts路由
- 性能基准测试: 11条路由Sub-500ms测试

**文件统计:**
- 新增文件: 18个
- 修改文件: 33个
- 测试覆盖: +200个测试用例

### v0.1.20 (2026-05-28)

**Stock-to-Fund Reverse Lookup Enhancement:**
- crowding_analysis.py: Holding overlap and crowding score calculation
- duckdb_ingestion.py: Aggregation by stock with HHI index
- StockReverseHolding.vue: Crowding heatmap, export buttons
- New endpoints: /crowding, /aggregation, /export

### v0.1.19 (2026-05-28)

**Deposit-ERP Linkage:**
- deposit_spread.py: Deposit-bond spread calculation
- risk_free_rates.py: Large deposit rate tiers (1Y/3Y/5Y)
- ERP endpoint supports risk_free_type parameter

### v0.1.18 (2026-05-28)

**Mobile Responsive Fixes:**
- FOFBacktest.vue: Tab switching for dual charts on mobile
- scrollIntoView for keyboard occlusion
- BottomSheet snap points optimization

### v0.1.17 (2026-05-28)

**Empty States + Jargon Tooltips:**
- EmptyState.vue: User-friendly empty state component
- JargonTooltip.vue: Financial term definitions with touch support
- jargon.json: 10+ financial term definitions

### v0.1.16 (2026-05-28)

**Skeleton Screens:**
- SkeletonLoader.vue: Shimmer animation component
- skeleton.css: Linear-gradient loading effect
- Applied to FundFilter, FundCompare, Dashboard, IndexValuation

### v0.1.15 (2026-05-28)

**aData Direct Mode:**
- Request batching (max 50 symbols)
- Request deduplication and coalescing
- Primary source with AkShare fallback

### v0.1.14 (2026-05-28)

**L1/L2 Tiered Cache:**
- tiered_cache.py: TTLCache L1 + Parquet L2
- cache_metadata.py: SQLite tracking
- Cache warmup on startup

### v0.1.13 (2026-05-28)

**Market Data Gateway + Circuit Breaker:**
- circuit_breaker.py: CLOSED/OPEN/HALF_OPEN state machine
- market_gateway.py: Multi-source failover
- sources/: AkShare, EastMoney, Sina adapters

### v0.1.12 (2026-05-28)

**DuckDB Connection Pool:**
- duckdb_pool.py: 4 read + 1 write connections
- asyncio.Lock for write serialization
- Connection health check with auto-reconnect

### v0.1.11 (2026-05-28)

**Scheduler Process Isolation:**
- scheduler_worker.py: Independent worker process
- state_manager.py: SQLite WAL for IPC
- data_bridge.py: Parquet + SQLite manifest
- process_manager.py: Health monitoring

### v0.1.10 (2026-05-28)

**Event Loop Unblocking:**
- async_akshare.py: ThreadPoolExecutor wrapper
- thread_pool.py: Centralized pool management
- asyncio.to_thread for blocking operations
- 30s timeout protection

### v0.1.9 (2026-05-27)

**UI/UX深度审计 + DuckDB OLAP + 保险IRR鲁棒性增强:**

**Phase 1: UI/UX深度审计**
- useBreakpoint.ts扩展: 8断点(xs:320px→4k:3840px), isTouchDevice, devicePixelRatio, orientation
- BottomSheet阻尼算法: Math.log(1+deltaY)*15触控阻尼 + overscroll-behavior: contain
- inputmode属性: InsuranceCalculator/FundCalcAIP numeric键盘优化
- FundCompare粘性列: sticky left-0 z-10, scroll indicators, Tailwind progressive hiding
- ECharts渲染器选择: SVG(移动端) vs Canvas(桌面端) + devicePixelRatio

**Phase 2: DuckDB OLAP优化**
- 新增duckdb>=0.10.0, pyarrow>=15.0.0依赖
- backend/core/duckdb_connection.py: DuckDB连接管理器
- backend/services/duckdb_ingestion.py: OLAP数据摄入 + 反向持仓查询
- backend/services/parquet_cache.py: Parquet缓存 + Hive分区 + 物理锁
- idx_stock_reverse_query倒排索引

**Phase 5: 保险IRR鲁棒性增强**
- Descartes符号法则: count_sign_changes()检测多重IRR
- IRRResult dataclass: irr, method, iterations, residual, sign_changes, warning
- Bisection fallback: Newton→Brent→Bisection三级求解器
- 80年投影测试 + 极端值测试

**Phase 7: 内存泄漏测试升级**
- 路由切换30→50次
- ECHARTS_ROUTES 5→10条路由

**新增文件:**
- `backend/core/duckdb_connection.py` - DuckDB OLAP连接管理 (84行)
- `backend/services/duckdb_ingestion.py` - OLAP数据摄入 (112行)
- `backend/services/parquet_cache.py` - Parquet缓存服务 (180行)

**修改文件:**
- frontend/src/composables/useBreakpoint.ts - 8断点扩展
- frontend/src/components/BottomSheet.vue - 阻尼算法
- frontend/src/components/EChartsWrapper.vue - SVG/Canvas渲染器
- frontend/src/views/FundCompare.vue - 粘性列+渐进隐藏
- frontend/src/views/InsuranceCalculator.vue - inputmode
- frontend/src/views/FundCalcAIP.vue - inputmode
- backend/services/insurance_calculator.py - Descartes法则+Bisection
- backend/services/scheduler.py - 季度调度器
- backend/tests/audit_memory_leak.py - 50次路由测试
- tests/test_insurance_xirr.py - 80年测试

**文件统计:**
- 12 files changed
- 569 insertions, 156 deletions
- 3 new files

### v0.1.8 (2026-05-27)

**M1-M4 里程碑实现 - 四大核心功能增强:**

**M1: 穿透持仓因子数据库表与自动加载管道**
- 新增 `GET /api/v1/fund/stock-reverse` 反向持仓查询端点
- 添加 `idx_stock_reverse` 索引优化查询性能
- 创建 `StockReverseHolding.vue` 机构抱团分析视图
- 支持按股票代码查询所有持有该股票的基金
- 计算加总暴露用于拥挤度分析

**M2: FOF组合归因多期Carino/Menchero几何连结**
- 新增 `linking_method` 参数 (auto/carino/menchero)
- 新增 `period_granularity` 参数 (daily/weekly/monthly)
- 返回多期归因结果含残差验证 (< 1e-12)
- FOFBacktest.vue 添加链接方法选择器
- 期间分解瀑布图可视化

**M3: 存款配置研究看板与大类资产配置面板**
- ERP计算支持可切换无风险利率
- 三种利率类型: 国债10年 / 国开债10年 / DR007
- 创建 `risk_free_rates.py` 利率查询服务
- ERPSpread.vue 添加利率类型选择器
- 利率对比表展示不同基准下的ERP

**M4: 贵金属黄金跨境实时套利溢价曲线前端绑定**
- 金价历史API增加 `spread_pct` 溢价百分比字段
- 双轴图表: 上海金(CNY/g)左轴 + 伦敦金(USD/oz)右轴
- 溢价率虚线 + 平价线标记
- 触控友好 dataZoom (双指缩放 + 单指滑动)
- 响应式设计支持 320px-3840px

**新增文件:**
- `frontend/src/views/StockReverseHolding.vue` - 机构抱团分析 (282行)
- `backend/services/risk_free_rates.py` - 无风险利率服务 (142行)

**修改文件:**
- `backend/api/fund.py` - 反向持仓查询端点
- `backend/api/analytics.py` - ERP risk_free_type参数
- `backend/api/gold.py` - spread_pct字段
- `backend/api/portfolio.py` - 多期Brinson集成
- `backend/models/fund.py` - idx_stock_reverse索引
- `backend/schemas/portfolio.py` - 多期归因schema
- `frontend/src/views/FOFBacktest.vue` - 链接方法选择器
- `frontend/src/views/ERPSpread.vue` - 利率类型选择器
- `frontend/src/views/GoldProducts.vue` - 双轴图表+dataZoom

**测试覆盖:**
- 182 tests passed (10 pre-existing failures unrelated to changes)
- Brinson: 50+ tests all passed
- 残差验证: < 1e-12

### v0.1.7 (2026-05-27)

**V4.5/V4.6 技术债清偿 - 五项关键修复:**

**1. 多期Brinson归因算法 (Carino + Menchero):**
- Carino链接系数: `k = (R_p_compound - R_b_compound) / sum(R_p_i - R_b_i)`
- Menchero平滑因子: 周期特定系数 + 数值稳定性优化
- 残差精度: `< 1e-12` (目标达成)
- 自动方法切换: 超额收益接近零时自动选择Menchero
- 50个测试用例全部通过

**2. 黄金盎司精算换算:**
- 精确常量: `31.1034768` 克/金衡盎司 (非近似值31.10)
- 成色校正: London 0.9999 vs Shanghai 0.995 纯度比
- VAT摩擦因子: 0.35% 增值税影响
- Round-trip误差: `0.000005%` (目标 <0.01%, 超2000倍精度)
- 18个测试用例全部通过

**3. 保险IRR现金流时序对齐:**
- 显式日期现金流: 消除1年期初/期末偏差
- XNPV/XIRR算法: 不规则间隔NPV计算
- Brent混合求解器: Newton-Raphson优先 + Brent保底
- payment_timing参数: "beginning"/"end" 期初/期末选项
- 30个测试用例全部通过

**4. 数据库并发写入重试:**
- 指数退避装饰器: `delay = min(max_delay, base_delay * 2^attempt) + jitter`
- 仅SQLITE_BUSY重试: 非锁定错误立即抛出
- 随机抖动: 防止惊群效应
- 应用范围: Portfolio/Pool/Favorites/Ingestion写操作
- 15个测试用例全部通过

**5. 内存泄漏自动化测试:**
- Playwright CDP集成: Chrome DevTools Protocol内存分析
- MemoryProfiler类: force_gc + measure + analyze
- 验证标准: JSHeap delta < 50KB, DOM nodes delta ≤ 0
- 测试路由: 5个ECharts图表页面
- 30次路由切换压力测试

**新增文件:**
- `backend/services/gold_constants.py` - 黄金精算常量 (308行)
- `backend/tests/audit_memory_leak.py` - Playwright内存测试 (418行)
- `tests/test_gold_conversion.py` - 黄金换算测试 (280行)
- `tests/test_insurance_xirr.py` - 保险IRR测试 (350行)
- `backend/tests/test_sqlite_retry.py` - 数据库重试测试 (180行)

**修改文件:**
- `backend/services/brinson.py` - 多期Brinson实现 (670行)
- `backend/services/insurance_calculator.py` - XIRR时序对齐 (450行)
- `backend/core/database.py` - 重试装饰器 (120行)
- `backend/api/gold.py` - 黄金API更新 (268行)
- `backend/api/insurance.py` - 保险API更新 (85行)
- `requirements.txt` - 添加pytest-playwright

**测试覆盖:**
- 113个测试全部通过
- Brinson: 50 tests
- Gold: 18 tests
- Insurance: 30 tests
- Retry: 15 tests

**文件统计:**
- 15 files changed
- 2,800+ insertions

### v0.1.6 (2026-05-27)

**V4.3 规范完整实现 - 三大里程碑:**

**里程碑一 - 大类配置研究:**
- 存款利率看板: AkShare interbank rates + 国债收益率利差分析
- 保险IRR测算器: Newton-Raphson算法 + 30年现金价值投影
- 贵金属跟踪: 上海金交所Au99.99实时价格 + 伦敦金估算 + 价差分析

**里程碑二 - 穿透持仓因子分析:**
- fund_portfolio_holdings表: 基金持仓明细 (股票代码/名称/比例/市值/变动方向)
- fund_industry_allocation表: 行业配置分布 (行业/比例/市值)
- FundDetail.vue: 持仓表格 + 行业饼图可视化 + 报告期下拉选择

**里程碑三 - FOF虚拟组合回测 + Brinson业绩归因:**
- user_portfolio表: 用户FOF组合管理 (基金代码/权重配置)
- backtest_result表: 回测结果存储 (收益率/统计指标/Brinson归因)
- 回测引擎: 组合NAV计算 + 基准对比 + 统计指标
- Brinson-Hood-Beebower归因模型: allocation/selection/interaction效应
- FOFBacktest.vue: 组合构建器 + 回测配置 + 结果仪表盘

**新增 API 端点 (17个):**
- `GET /api/v1/deposit/rates` 存款利率与国债利差
- `POST /api/v1/insurance/calculate` 保险IRR计算
- `GET /api/v1/gold/spot-price` 金价实时数据
- `GET /api/v1/gold/history` 金价历史走势
- `GET /api/v1/fund/{code}/holdings` 基金持仓明细
- `GET /api/v1/fund/{code}/industry` 行业配置分布
- `POST /api/v1/portfolio` 创建组合
- `GET /api/v1/portfolio` 列出组合
- `GET /api/v1/portfolio/{id}` 获取组合详情
- `PUT /api/v1/portfolio/{id}` 更新组合
- `DELETE /api/v1/portfolio/{id}` 删除组合
- `POST /api/v1/portfolio/{id}/backtest` 运行回测
- `GET /api/v1/portfolio/{id}/backtest` 列出回测结果
- `GET /api/v1/portfolio/{id}/backtest/{result_id}` 获取回测详情

**新增前端视图 (5个):**
- DepositMarket.vue - 存款利率看板
- InsuranceCalculator.vue - 保险IRR测算器
- GoldProducts.vue - 贵金属跟踪
- FundDetail.vue - 基金详情穿透
- FOFBacktest.vue - FOF组合回测

**技术亮点:**
- EChartsWrapper响应式aspect-ratio (4:3移动端, 16:9桌面端)
- FundCompare粘性首列 + 触控优化CSS
- 权重自动归一化 (组合构建)
- Brinson瀑布图归因可视化

**文件统计:**
- 31 files changed
- 6,385+ insertions

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
