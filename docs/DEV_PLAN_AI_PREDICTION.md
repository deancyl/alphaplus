# Alphaplus 开发计划：AI 走势分析预测 + 工程哲学对齐

> 依据：`example/research-terminal-src-20261013` 案例（口径正确性 + 失败诚实声明 + 单一实现 + 统一契约）
> 最终目标：为平台的数据支持增加「AI 走势分析预测」能力（LLM 或客观经济学模型）
> 内部测试端口：**60100**
> 原则：边开发、边回顾、边解决问题；不填占位假数据。

---

## 0. 基线（本次开始前实测）

`backend/tests` 逐文件结果：

| 文件 | 结果 | 归类 |
| --- | --- | --- |
| test_adata / aip / api / brinson / brinson_validation / config_warmup / correlation / deposit_erp / duckdb_pool / factor_exposure / favorites / formatters / index_valuation / new_high_ratio / pool / resilience / simulators / sqlite_retry / wmp_filter | 全绿 | ✅ |
| test_async_blocking | 1 failed（并发 0/10，网络/代理） | ⚠️ 环境 |
| test_market_gateway | 1 failed（half-open 未关闭） | 🐛 真实缺陷 |
| test_models | 2 failed（测试库已存在 → UNIQUE） | 🐛 测试隔离缺陷 |
| test_warmup_refactor | 2 failed（断言源码字符串） | 🐛 脆弱测试 |
| test_performance | 15 failed（需 60201 前端在跑，Playwright） | ⚠️ 环境 |
| test_cache_performance | 挂起（无 pytest-timeout） | 🐛 无超时保护 |

结论：**基线非全绿**，本计划把上述归为"待修债务"，不阻塞新功能主线。

---

## 1. 阶段划分

### Phase 1 — 工程质量对齐（research-terminal 的三条硬约束）

- **P1.1 统一响应信封 + 白名单错误码**（对应 `ok()/fail()/safeErrorCode()`）
  - 新增 `backend/core/envelope.py`：`ok(action, data, **extra)` / `fail(action, error, status)`。
  - 新增全局异常处理器，把未预期异常归一为 `runtime_<ErrorName>`，**不泄漏堆栈/URL**。
  - 新增端点走信封；存量端点保持兼容（渐进迁移，不破坏 40+ 端点与前端）。
- **P1.2 声明式降级（去掉"假数据当真实"）**
  - `warmup_fallback` / `simulators` 的注入数据一律带 `is_simulated=true` + `source="simulated"`。
  - 新增 `settings.allow_simulated_fallback`（默认 `false`）；关闭时上游失败返回"该数据源不可用"+错误码，而不是随机路径。
- **P1.3 口径外部锚点验收测试**
  - 复权净值 vs 东财公布阶段涨幅逐窗口对齐（阈值 ≤ 0.005%），对齐 `verify_fund.ts` 思路。

### Phase 2 — 走势分析与预测（本计划核心）

- **P2.1 特征工程**（`backend/services/forecast.py`）
  - 从真实日线序列计算：对数收益、年化漂移 μ、年化波动 σ、区间分位、偏离度 z、Hurst（DFA）、趋势/震荡状态。
- **P2.2 非 LLM 经济学模型（客观规律，默认可用）**
  - 均值回归分量（估值/均线偏离 z）＋ 历史漂移，输出**分位数路径带**（p10/p25/median/p75/p90）而非点估计。
  - 经验分位用历史收益 bootstrap（保留厚尾），不假设正态。
  - 每条结论附 `basis`（口径）与 `limits`（边界）。
- **P2.3 LLM 分析层（OpenAI 兼容，可选）**
  - `backend/services/llm_client.py`：支持 **chat/completions** 与 **responses** 两种格式，`base_url`/`api_key`/`model` 从环境变量读取。
  - 把 P2.1/P2.2 的**结构化结果**作为 context，让模型只做"解读"，不编造数值。
  - 未配置密钥时**诚实降级**：返回 `enabled=false` + 原因，绝不伪造解读。
- **P2.4 API**：`GET /api/v1/analytics/forecast/{index_code}`（走信封）。
- **P2.5 前端**：`Forecast.vue` + 路由 + 菜单（`/market/forecast`）。

### Phase 3 — 验证与交付

- 后端单测（`test_forecast.py`，含外部锚点与降级行为）。
- 在 **60100** 端口起服务，端到端 smoke（后端 + 前端）。
- 提交并推送到 GitHub（`origin`）。

---

## 2. 端口约定

| 用途 | 端口 |
| --- | --- |
| 生产/日常后端 | 60200 |
| 生产/日常前端 | 60201 |
| **内部测试（本次开发/集成）** | **60100**（后端） |

`settings.test_port = 60100`；集成脚本 `scripts/dev_60100.sh` 在后端与前端均使用 60100。

---

## 3. 验收标准（对照目标逐条）

1. 计划落地到本文件 ✅
2. 统一信封 + 白名单错误码，且新端点生效 ✅（`backend/core/envelope.py` + 全局异常处理器；旧 `detail` 字段保留兼容）
3. 声明式降级：默认不再用假数据冒充真实；`is_simulated` 全程可辨 ✅（`allow_simulated_fallback=False` 默认；`mark_simulated()` 打标）
4. AI 走势预测功能：后端服务 + API + 前端页面，可在 60100 验证 ✅
5. 口径外部锚点验收测试存在且有断言 ✅（`scripts/verify_nav_anchor.py` + `backend/tests/test_nav_anchor.py`）
6. 提交并推送到 GitHub ✅（main @ 9809fda，含 3 个提交）

---

## 4. 交付物清单（本次）

| 文件 | 作用 |
| --- | --- |
| `backend/core/envelope.py` | 统一信封 `ok()/fail()` + 白名单错误码 `safe_error_code()` |
| `backend/main.py` | 全局异常处理器（HTTP/校验/未捕获），保留旧 `detail` 兼容 |
| `backend/services/forecast.py` | 客观经济模型：漂移+均值回归、经验分位带、Hurst(DFA) |
| `backend/services/llm_client.py` | OpenAI chat/responses 双格式客户端，无密钥诚实降级 |
| `backend/api/forecast.py` | `GET /api/v1/analytics/forecast/{index_code}` |
| `backend/services/warmup_fallback.py` | `mark_simulated()`：模拟数据全程打标 |
| `backend/services/akshare_data.py` | `get_index_daily_history()`：失败返回空而非模拟 |
| `frontend/src/views/Forecast.vue` | 预测页面（分位路径带 + 模型构成 + AI 解读 + 口径/局限） |
| `scripts/verify_nav_anchor.py` | 外部锚点验收（复权收益 vs 东财公布值） |
| `scripts/verify_llm.py` | LLM 双格式契约验证（本地 mock） |
| `scripts/dev_60100.sh` | 60100 端口一键启动（后端同时托管构建后的前端） |
| `scripts/smoke_forecast_ui.py` | 60100 端到端 UI 冒烟 |

---

## 5. 验证证据（实测）

- 外部锚点：12 只基金 × 5 个收益窗口，最大误差 **0.005pp**（阈值 0.05pp），`EXIT=0`。
- 单元/契约：`test_forecast.py` 22 passed；`test_nav_anchor.py` 6 passed。
- 60100 端到端：forecast 端点 `ok=true`；非法指数 → 400 `invalid_index_code`；未知路由 → 404 `not_found`。
- LLM：本地 mock 验证 chat 与 responses 两种格式均成功；无密钥时 `llm_not_configured`。
- 前端：`npm run build` 通过；Playwright 冒烟确认页面渲染（截图 `/tmp/opencode/forecast_60100.png`）。

