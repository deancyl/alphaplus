# Alphaplus 设计标准文档

**版本**: v1.0  
**创建日期**: 2026-05-28  
**目的**: 定义关键设计模式防止技术债务积累

---

## 1. 启动流程标准

### 1.1 非阻塞启动原则

**规则**: 任何启动操作不得阻塞服务就绪状态超过 5 秒。

**违规案例 (已修复)**:
- `_warmup_cache()` 阻塞启动 30+ 秒等待外部API
- AkShare 调用失败导致服务崩溃

**正确实现**:
```python
async def startup_task():
    # 立即注入降级数据
    _inject_fallback_data()
    
    # 后台异步执行
    asyncio.create_task(background_warmup())
```

### 1.2 启动配置参数

| 参数 | 强制值 | 原因 |
|------|--------|------|
| `warmup_timeout_seconds` | ≤ 10 | 防止长时间阻塞 |
| `warmup_retry_count` | ≤ 1 | 减少外部依赖风险 |
| `warmup_blocking` | `false` | 默认非阻塞模式 |

---

## 2. 外部API调用标准

### 2.1 调用保护原则

**规则**: 所有外部API调用必须有:
1. 超时保护 (`asyncio.wait_for`)
2. 异常捕获 (不传播到启动流程)
3. 降级数据备选

**示例**:
```python
async def fetch_with_fallback():
    try:
        data = await asyncio.wait_for(
            external_api_call(),
            timeout=10.0
        )
        return data
    except (TimeoutError, Exception):
        return get_fallback_data()
```

### 2.2 禁止模式

❌ **禁止**: 启动时直接调用外部API无超时
❌ **禁止**: 启动失败直接抛出异常崩溃
❌ **禁止**: 同步阻塞调用 (在async函数中使用 `requests`)

---

## 3. 降级数据设计原则

### 3.1 Fallback数据要求

**必须包含**:
- 明确的 `is_fallback=True` 标记
- 合理的默认值 (非异常值)
- 时间戳标记

**示例结构**:
```python
{
    "index_code": "000300",
    "pe_ttm": 15.0,  # 合理默认值
    "is_fallback": True,  # 明确标记
    "timestamp": datetime.now().isoformat()
}
```

### 3.2 核心指标默认值

| 指标 | 默认值 | 原因 |
|------|--------|------|
| PE百分位 | 50.0 | 中位数代表"正常"估值 |
| 恐惧贪婪 | 50.0 | 中性情绪 |
| 指数涨跌 | 0.0 | 无变化状态 |

---

## 4. 配置层扩展原则

### 4.1 配置参数命名规范

**格式**: `<功能模块>_<具体参数>_<单位/后缀>`

**正确示例**:
- `warmup_timeout_seconds`
- `fear_greed_history_days`
- `gold_shanghai_purity`

**错误示例**:
- `timeout` (无模块前缀)
- `warmupTimeout` (混用驼峰)

### 4.2 禁止硬编码

**规则**: 所有业务参数必须通过 Settings 配置化。

**检查清单**:
- [ ] 指数代码列表 (已配置: `CORE_INDICES`)
- [ ] 预热基金数量 (已配置: `warmup_top_funds_count`)
- [ ] 历史数据天数 (已配置: `fear_greed_history_days`)

---

## 5. 检查与审计流程

### 5.1 新功能PR检查项

- [ ] 启动时间 < 5秒 (无阻塞)
- [ ] 外部调用有超时保护
- [ ] 配置参数在 Settings 定义
- [ ] 有降级数据备选方案

### 5.2 代码审查重点

1. `main.py` 的 `lifespan()` 函数是否非阻塞
2. `asyncio.create_task` vs `await` 的正确使用
3. 异常是否传播到启动流程

---

## 6. 参考文档

- README.md "启动优化" 章节
- backend/services/warmup_fallback.py
- backend/core/config.py

---

## 7. 数值格式化标准

### 7.1 小数位数规范

| 数据类型 | 小数位数 | 使用场景 |
|----------|----------|----------|
| **价格** | 2位 | 指数价格、基金净值、股票价格 |
| **百分比** | 2位 | 涨跌幅、收益率、PE百分位 |
| **评分** | 1-2位 | 恐惧贪婪指数、拥挤度 |
| **相关性** | 4位 | Pearson相关系数 |
| **因子权重** | 4位 | 因子暴露权重 |
| **黄金纯度** | 6位 | 黄金成色系数 (domain-specific) |

### 7.2 后端格式化规则

**使用 `backend/utils/formatters.py`**:

```python
from backend.utils.formatters import round2, round4

# 价格、百分比、收益 → 2位小数
price = round2(100.12345)  # 100.12

# 相关性、因子权重 → 4位小数  
correlation = round4(0.123456)  # 0.1235
```

**禁止模式**:
❌ `round(x, 2)` - 使用 `round2(x)` 替代
❌ `round(x, 4)` - 使用 `round4(x)` 替代
❌ 在Pydantic schema中缺少validator

### 7.3 前端格式化规则

**使用 `frontend/src/utils/formatters.ts`**:

```typescript
import { formatNumber, formatPercent, formatPrice } from '@/utils/formatters'

// 基本格式化
formatNumber(1.2345)  // '1.23'
formatPercent(50.123)  // '50.12%'
formatPrice(100.123)  // '100.12'

// 带符号格式化
formatSign(1.23)  // '+1.23'
formatSignPercent(1.23)  // '+1.23%'
```

**禁止模式**:
❌ 组件内定义本地 `formatNumber` 函数
❌ 内联使用 `.toFixed(2)` - 使用 `formatNumber()` 替代
❌ 重复导入未使用 centralized formatters

### 7.4 ECharts 格式化规则

```typescript
// Tooltip formatter
formatter: (params: any) => {
  return `${params.name}: ${formatNumber(params.value)}`
}

// Axis label formatter
axisLabel: {
  formatter: (value: number) => formatNumber(value)
}
```

### 7.5 PR检查清单

- [ ] 所有float字段有Pydantic validator
- [ ] 服务层使用 `round2()`/`round4()` 而非 `round()`
- [ ] 前端组件导入自 `@/utils/formatters`
- [ ] 无本地 `formatNumber` 函数定义
- [ ] ECharts formatters 使用 centralized utility
