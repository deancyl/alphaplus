# Alphaplus 故障排查指南

**版本**: v1.0
**创建日期**: 2026-05-28

---

## 1. 启动问题排查

### 1.1 服务启动超时 (> 10秒)

**症状**: `uvicorn` 启动后长时间无响应

**排查步骤**:

1. 检查预热配置:
   ```bash
   grep warmup backend/core/config.py
   ```

2. 确认非阻塞模式:
   ```python
   # config.py 应显示:
   warmup_blocking: bool = False
   ```

3. 检查外部API状态:
   ```bash
   curl -v https://akshare-api.example.com
   ```

**解决方案**:
- 设置 `warmup_blocking=False`
- 设置 `warmup_timeout_seconds=10.0`
- 检查网络代理配置

### 1.2 启动时服务崩溃

**症状**: `RuntimeError` 或 `Exception` 在 `lifespan()`

**排查步骤**:

1. 查看启动日志:
   ```bash
   python -m uvicorn backend.main:app --log-level debug
   ```

2. 检查异常来源:
   - `_warmup_cache()` 函数
   - 外部API调用失败
   - 数据库连接失败

**解决方案**:
- 确认 `warmup_fallback_enabled=True`
- 检查数据库路径权限
- 禁用外部API预热: `warmup_enabled=False`

---

## 2. 外部API问题排查

### 2.1 AkShare API超时

**症状**: API调用返回超时或空数据

**排查步骤**:

1. 测试API连通性:
   ```python
   import akshare as ak
   ak.stock_zh_a_spot_em()
   ```

2. 检查代理设置:
   ```bash
   echo $HTTP_PROXY $HTTPS_PROXY
   ```

3. 检查限流状态:
   ```python
   # 查看限流器日志
   grep "rate_limiter" logs/*.log
   ```

**解决方案**:
- 使用降级数据模式
- 检查代理是否需要认证
- 增加限流窗口: `akshare_rate_limit=5`

### 2.2 降级数据识别

**症状**: 数据显示不合理或标记为 `is_fallback`

**识别方法**:
```python
# 检查数据源
response = requests.get("/api/v1/market/index-valuation")
data = response.json()
if data[0].get("is_fallback"):
    print("使用降级数据")
```

**恢复方法**:
- 等待后台预热完成
- 手动刷新: 点击前端"刷新数据"按钮
- 检查外部API恢复状态

---

## 3. 配置问题排查

### 3.1 环境变量未生效

**症状**: 配置参数值与预期不符

**排查步骤**:

1. 检查环境变量:
   ```bash
   env | grep WARMUP
   ```

2. 检查.env文件:
   ```bash
   cat .env | grep warmup
   ```

3. 验证Settings加载:
   ```python
   from backend.core import settings
   print(settings.warmup_timeout_seconds)
   ```

**解决方案**:
- 确保.env文件编码为UTF-8
- 检查环境变量命名格式
- 重启服务加载新配置

---

## 4. 参考文档

- docs/design-standards.md - 设计原则
- README.md "启动优化" 章节
- backend/core/config.py - 配置定义
