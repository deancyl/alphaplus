# 实时数据获取架构研究：research-terminal → Alphaplus

> 目标：学习 `example/research-terminal-src-20261013/research-terminal` 中「几乎所有数据都是实时获取」的优势，
> 据此改造 Alphaplus，使全部数据端点实时获取（或诚实声明不可用）。
> 验证端口：**60100**。

---

## 一、research-terminal 的实时架构（它做对了什么）

### 1.1 一句话概括

**仓库里没有任何数据文件。** 18 个 action 的每一个数字，都在请求时刻从 15 个硬编码白名单上游抓回来；
抓不到就降级并**在响应里写明哪个源失败**；只有**全部**源失败才整体报错。前端从不直连第三方。

### 1.2 三层结构

```
浏览器  web/（纯静态，无构建）
   │  fetch(`/functions/v1/app?action=…`)   ← 全部同源相对路径
   ▼
边缘函数  functions/handler.ts   路由 + 18 action + TTL 缓存 + 信封 + 降级
   │
   ▼
上游白名单  functions/sources.ts  ALLOWED_HOSTS（15 个主机，https-only，重定向后必须仍在白名单）
```

关键点：**取数目标是代码里的白名单，浏览器无法指定 URL**，所以这个函数永远不会变成开放代理。

### 1.3 实时性的五个支柱

| 支柱 | 实现 | 位置 |
| --- | --- | --- |
| **① 请求时抓取** | 没有预物化的快照表。每个 action 在请求时刻调上游 | `sources.ts` |
| **② 每条数据有备用源** | 指数：腾讯 `qt.gtimg.cn` 主用 → push2 镜像轮换备用；日K：腾讯 → 新浪；基金档案：`pingzhongdata` 一次整包 → `f10/lsjz` 分页 | `quoteWithFallback` / `fetchDailyBars` / `fetchFundDetail` |
| **③ 分级 TTL，且**不缓存错误**** | 实时 30s、日线/基金 5min、汇率 1h；`attempt()` 失败返回 `{data:null,error}`，**错误从不写进缓存** | `REALTIME_TTL/DAILY_TTL/FX_TTL`、`cached()` |
| **④ 按源降级** | `overview` 用 `Promise.all + attempt` 并行 6 个源，**部分失败只让对应卡片显示「该数据源本次不可用」**，响应里带 `sources:{name:{status,error}}`；**全部**失败才 502 | `attempt()` / `overviewAction` |
| **⑤ 来源必须披露** | `barSource: tencent\|sina\|sina_unadjusted`（新浪无前复权，绝不假装有）；`breadth: fenbu\|exchange`；`temperatureInputs`；`runtime.quoteHost` = 最后一次快照实际由哪台主机服务 | `fetchDailyBars` / `overview` / `health` |

### 1.4 统一信封与白名单错误码

```jsonc
// 成功
{ "ok": true,  "action": "fund", "generatedAt": "…Z", ...action 自己的字段 }
// 失败
{ "ok": false, "action": "fund", "error": "no_nav_history", "generatedAt": "…Z" }
```

`safeErrorCode()` **只透传**匹配 `^(upstream|invalid|no_bars|unknown_action|method_not_allowed|missing_)` 的已知码，
其余归一为 `runtime_<ErrorName>`。上游原始报错文本、URL、堆栈**永远不会**顺着 JSON 漏到浏览器。

### 1.5 `action=health` —— 实时性的自证

```jsonc
{ "targets": [{ "id":"kline", "status":"up|empty|down", "ms":12, "records":250, "error":"upstream_503" }],
  "hosts":    [{ "host":"qt.gtimg.cn (腾讯)", "ok":true, "ms":41 }, … 6 台 push2 镜像],
  "checkedAt":"…Z",
  "runtime":  { "quoteHost": "qt.gtimg.cn", … } }
```

**逐台探测每个上游并回报耗时**，`runtime.quoteHost` 写明最后一次快照由谁服务。
这就是「实时」可被验证的地方——不是靠口头宣称，而是靠一份每次都现测的探针结果。

### 1.6 能力边界三档声明

`✓ 已提供 · ! 有口径限制 · ✕ 未提供（不用占位数据伪造）`

wiki `07-能力边界与故障排查.md` 把「为什么没有」逐条写清楚。**拿不到就进 `available`/`boundaries`/`limits` 并在页面上说明，绝不填占位值。** 这是它最核心的一条承诺。

### 1.7 每个上游坑都被文档化

- `qt.gtimg.cn` 返回 GBK，运行时不支持 `gbk` 标签时退回 UTF-8：**数字仍正确，只有中文名退化** —— 所以不改成抛错。
- 北证50 必须 `bj899050`（`sh899050` 返回空）；腾讯对它只给 1 根 K 线 → 自动走新浪。
- `rankhandler.aspx` 是**位置数组**，跳一个下标会把近6月显示在近3月下 —— 这是**上过线的生产 bug**。
- `f10/lsjz` 的 `pageSize` 超过约 200 返回 `Data:null`，取长历史必须翻页而不是调大参数。
- 边缘运行时可达性与本机不同：`push2` 集群从边缘全挂，所以把腾讯设为主用。**本地能跑通不代表线上能跑通。**

---

## 二、本机（60100 所在环境）上游可达性实测

改造前先确认「实时」在本机是否可行。实测（已 unset 全部 proxy 变量）：

### 2.1 HTTP 主机层（research-terminal 全部白名单）

| 主机 | 结果 | 耗时 | 说明 |
| --- | --- | --- | --- |
| `qt.gtimg.cn` | ✅ OK | 260ms | 腾讯批量实时行情（GBK） |
| `web.ifzq.gtimg.cn` | ✅ OK | 278ms | 腾讯日K线（前复权可选） |
| `push2.eastmoney.com` | ✅ OK | 365ms | 东财 `ulist.np/get` |
| `82.push2.eastmoney.com` | ✅ OK | 357ms | 镜像可用，可轮换 |
| `push2ex.eastmoney.com` | ✅ OK | 329ms | **全市场涨跌家数分布 `getTopicZDFenBu`** |
| `vip.stock.finance.sina.com.cn` | ✅ OK | 320ms | 新浪日K + 涨幅榜 |
| `hq.sinajs.cn` | ✅ OK | 219ms | 新浪快照 |
| `fund.eastmoney.com/data/rankhandler.aspx` | ✅ OK | 1904ms | 基金排行 |
| `api.fund.eastmoney.com/f10/lsjz` | ✅ OK | 130ms | 基金净值分页 |
| `fund.eastmoney.com/pingzhongdata/{code}.js` | ⚠️ 断流 | — | gzip 截断（`EOFError`），需重试或走分页备用 |
| `www.chinamoney.com.cn` | ✅ OK | 180ms | 人民币中间价 |
| `api.frankfurter.dev` | ✅ OK | 1405ms | ECB 参考汇率 |

> **结论：research-terminal 的实时架构在本机完全可行**，包括它认为「边缘不可达」的 push2 集群。
> 因此 Alphaplus **没有任何理由**继续读 5 个月前的快照表。

### 2.2 akshare 函数层

| 调用 | 结果 | 耗时 | 最新数据 |
| --- | --- | --- | --- |
| `stock_zh_index_daily(sh000300)` | ✅ | 558ms | **2026-10-16（今日）** |
| `bond_china_yield` | ✅ | 2996ms | 2026-10-16 |
| `bond_zh_us_rate` | ✅ | 317ms | 2026-10-16 |
| `fund_open_fund_rank_em` | ✅ | 4064ms | 2026-10-16 |
| `futures_main_sina(RB0)` / `futures_zh_daily_sina` | ✅ | 344ms | 2026-10-16 |
| `macro_china_gdp` | ✅ | 372ms | 季度级（口径天然滞后） |
| `stock_zh_index_daily_em` | ❌ | 159ms | 东财指数日线（连接被切断）→ 改用腾讯/新浪 |
| `index_zh_a_hist` (东财) | ❌ | 7.1s | 同上 → 改用腾讯 `fqkline` |
| `stock_zh_a_spot_em`（全市场快照/宽度） | ❌ | 7.8s | 同上 → 改用 `push2ex/getTopicZDFenBu` |
| `stock_margin_sse`（两融） | ❌ | 615ms | 上游返回空表 |

> **教训与 research-terminal 完全一致：主机可达 ≠ akshare 函数可用。** 东财 `push2` 系 akshare 封装在本机全部失败，
> 但**同一主机的原始 HTTP 接口全部可用**。所以正确的做法是像 research-terminal 一样**直接调上游 HTTP**，而不是继续依赖 akshare 的东财封装。

---

## 三、Alphaplus 现状：与 research-terminal 的差距

### 3.1 最严重的问题：8 张「市场口径表」被冻结在 2026-05-25

`data/alphaplus.db` 全表扫描（23 张表）：

| 表 | 行数 | 最新日期 | 距今 |
| --- | --- | --- | --- |
| `market_fear_greed_sentiment_history` | 30 | 2026-05-25 | **~5 个月** |
| `market_style_strength_history` | 100 | 2026-05-25 | **~5 个月** |
| `bond_equity_yield_spread_history` | 100 | 2026-05-25 | **~5 个月** |
| `index_valuation_history` | 2000 | 2026-05-25 | **~5 个月** |
| `market_crowding_valuation_history` | 240 | 2026-05-26 | **~5 个月** |
| `money_market_rates` | 50 | 2026-05-25 | **~5 个月** |
| `fund_nav_history` | 262 | 2024-12-31 | **~21 个月** |
| `fund_portfolio_holdings` | 10 | 2024-03-31 | **~31 个月** |
| `bond_credit_spread_history` | **0** | — | 空表 |
| `bond_yield_curve_structure` | **0** | — | 空表 |
| `fund_issue_pipeline` | **0** | — | 空表 |
| `backtest_result` / `stock_quotes_history` / `market_calendar` | **0** | — | 空表 |

**根因**：`grep` 全仓库确认**没有任何代码 INSERT 这 8 张市场口径表**。
它们是被外部一次性灌入的（2026-05-25），此后 `scheduler_enabled=False`（`core/config.py:30`），
调度器从不启动，于是它们永久冻结。

**而 API 却宣称它们是活的**：

```python
# api/market.py:1010（fear-greed）、1062（erp）、1114（crowding）、1164（style-strength）
response = {"data": data, "_meta": {"is_fallback": False, "source": "database"}}
```

`is_fallback: False` 是**假话**——这不是降级，这是唯一的数据来源，而且已经 5 个月没动。
`analytics.py` 的 `fear-greed / erp / crowding / style-strength` 读**同一批表**，同样陈旧。

### 3.2 未受 `allow_simulated_fallback` 门禁的伪造数据

上一阶段把 `allow_simulated_fallback` 默认设为 `False` 并给 `warmup_fallback.inject_fallback_data()`
统一打了 `mark_simulated()`。但**有 5 条路径绕过了这道门禁直接返回伪造值**：

| 位置 | 伪造内容 | 门禁 |
| --- | --- | --- |
| `api/market.py:498` `/heatmap` | 5s 超时后无条件返回 `get_fallback_heatmap()` 静态热力图，还按 `ttl=3600` 写进缓存 | ❌ **无** |
| `services/bond_data.py:45` `/bond/credit-spread` | 库里没数据就返回 `get_fallback_credit_spread()` | ❌ **无** |
| `api/market.py:449` `/bond/issuance` | 异常时返回 `get_fallback_bond_issuance()` | ❌ **无** |
| `services/gold_constants.py:106` | 汇率取不到就用硬编码 `DEFAULT_USDCNY_FALLBACK = 7.20`，金价随之系统性偏差，且 `is_simulated` 仍为 `False` | ❌ **无** |
| `services/correlation.py:182` | 模拟返回空就用「fallback correlation」 | ❌ **无** |

### 3.3 缺少 research-terminal 的「可验证实时性」

| 能力 | research-terminal | Alphaplus（改造前） |
| --- | --- | --- |
| 每个响应带 `asOf` / 来源 | ✅ `generatedAt` + `barSource` + `breadth` + `quoteHost` | ❌ 绝大多数端点返回裸数组，无信封、无 as-of、无来源 |
| 上游健康自检 | ✅ `action=health` 逐台探测 + 耗时 + 最后服务主机 | ⚠️ 有 `/market/indices/health`（只探指数）、`/gateway/status`（只看熔断器状态），**没有全局探针** |
| 白名单错误码 | ✅ `safeErrorCode()` 只透传已知码 | ⚠️ 部分端点把 `str(e)` 直接塞进响应（`api/market.py:304`） |
| 主机白名单 | ✅ `ALLOWED_HOSTS` 15 项，https-only，重定向校验 | ❌ 无统一白名单层，各服务各调各的 |
| 多源备用 | ✅ 每条数据都有主/备 | ❌ 指数走单一 akshare 东财封装（本机正好是坏的那条） |
| 能力边界声明 | ✅ 三档 `✓ / ! / ✕` | ⚠️ 零散（`unavailable[]` 只在 deposit 出现过） |

### 3.4 性能：实时但慢

首次（冷）调用实测：

| 端点 | 耗时 | 说明 |
| --- | --- | --- |
| `/market/futures/quotes` | **36.8s** | 逐个合约串行抓取 |
| `/market/index-valuation` | **22.2s** | 逐指数串行抓 PE/PB/股息率 |
| `/deposit/rates` | **13.1s** | |
| `/gold/spot-price` | 8.5s | 已加 60s 缓存（上一阶段） |
| `/market/gateway/global` | 7.7s | |
| `/market/domestic` | 3.3s | |

research-terminal 的对应值：`REALTIME_TTL=30s` 内全部命中，未命中也基本 < 2s（并发 + 批量接口）。
**差距 = 串行循环 vs 批量/并发 + 每上游超时未钳制。**

---

## 四、改造方案（按 research-terminal 的支柱逐条对齐）

| # | 支柱 | Alphaplus 改造 |
| --- | --- | --- |
| **P1** | 请求时抓取，不读冻结表 | 8 个陈旧端点改为**请求时实时计算**：从腾讯/新浪/东财原始 HTTP 抓基础序列 → 服务端算指标。冻结表不再作为数据源（保留为可选历史补充，且必须披露 as-of） |
| **P2** | 每条数据有备用源 | 新建 `services/quote_sources.py`：`qt.gtimg.cn` 主用 → `push2` 镜像轮换备用（照搬 `quoteWithFallback` + `push2Cursor`），并返回**实际服务主机** |
| **P3** | 分级 TTL + 不缓存错误 | 沿用已有 `RealtimeCache`（per-key TTL 已修）；确保**失败不写缓存**，改为短负缓存（30s）以避免击穿 |
| **P4** | 按源降级 | 每个多上游端点的响应带 `sources: {name: {status, asOf, error}}`；**部分失败只声明该部分不可用**，不再整体假成功或整体 500 |
| **P5** | 来源必须披露 | 统一信封：`{ok, action, generatedAt, asOf, source, sources, data}`。`asOf` = 数据自身的业务日期（不是响应生成时间） |
| **P6** | 白名单错误码 | 新建 `services/upstream.py`：主机白名单 + https-only + 重定向校验 + 8s 超时 + `safe_cause()` 归一化错误码 |
| **P7** | `action=health` | 扩展 `/api/health`：逐台探测全部上游并回报耗时 + 最后服务主机 + 各端点 as-of |
| **P8** | 能力边界三档 | 伪适数值要么改为实时，要么打 `mark_simulated` 并受 `allow_simulated_fallback` 门禁，要么进 `unavailable[]` 明确声明 |

### 优先级

1. **P1 + P5**（最高）：8 个冻结端点实时化 + 统一信封披露 as-of —— 这是「所有数据实时」的主体。
2. **P8**：堵住 5 条绕过门禁的伪造路径。
3. **P2 + P6**：多源备用 + 主机白名单层。
4. **P7**：全局健康探针（实时性的自证）。
5. **性能**：把 36.8s / 22.2s 的串行抓取改成批量/并发 + 超时钳制。

---

## 五、验收口径

- 每个端点实测记录：`status` / `latency` / **`asOf`（业务日期）** / `source` / `sources[]`。
- 判定：`asOf` 必须是**当日或最近一个交易日**（宏观/季报类天然滞后，必须在 `limits` 里声明滞后原因）。
- 凡 `asOf` 早于最近交易日且无声明 → 判为不合格。
- 回归测试全绿；`git push origin main`。

> **本页记录的是改造前的诊断与方案。** 各端点逐条的最终实测结果见 `docs/REALTIME_ENDPOINT_AUDIT.md`。
