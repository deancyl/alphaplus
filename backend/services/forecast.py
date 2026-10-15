"""
Forecast service: objective, data-grounded trend analysis for indices.

Design follows the research-terminal case study:

* **Every number is computed from a real series.** No fabricated paths, no
  placeholder constants. If the upstream series cannot be fetched and caching
  cannot help, the action fails with ``no_bars`` / ``unavailable`` instead of a
  made-up curve.
* **Uncertainty is shown, not hidden.** The projection is an *empirical
  quantile band* (p10/p25/median/p75/p90) built by bootstrapping realised
  daily returns — fat tails are preserved because we resample history rather
  than assuming normality.
* **The economic model is stated.** A drift + mean-reversion blend, each
  component reported with its own weight and rationale, so a reader can see
  *why* the central path slopes the way it does.
* **The LLM only interprets.** Numeric context produced here is handed to the
  LLM layer; the model never invents prices. With no API key configured the
  endpoint says so instead of pretending to have an AI read.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
# Default look-back used to estimate drift / volatility.
DEFAULT_LOOKBACK = 500
# Horizon (trading days) exposed by default; frontend may ask for less.
DEFAULT_HORIZON = 20
MAX_HORIZON = 120
MIN_OBSERVATIONS = 60  # below this we refuse rather than guess


class ForecastError(Exception):
    """Raised when a forecast cannot be produced honestly."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message


# --- pure numeric helpers (kept dependency-free and testable) -----------------

def to_log_returns(prices: Sequence[float]) -> np.ndarray:
    """Daily log returns, ignoring non-positive / non-finite samples."""
    arr = np.asarray(prices, dtype=float)
    arr = arr[np.isfinite(arr) & (arr > 0)]
    if arr.size < 2:
        return np.empty(0, dtype=float)
    return np.diff(np.log(arr))


def annualised_drift(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    return float(returns.mean() * TRADING_DAYS)


def annualised_volatility(returns: np.ndarray) -> float:
    if returns.size < 2:
        return 0.0
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def max_drawdown(prices: Sequence[float]) -> float:
    arr = np.asarray(prices, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0
    running_max = np.maximum.accumulate(arr)
    drawdowns = arr / running_max - 1.0
    return float(drawdowns.min())


def zscore(value: float, sample: Sequence[float]) -> Optional[float]:
    """Standardised distance of ``value`` from the mean of ``sample``."""
    arr = np.asarray(sample, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return None
    sd = float(arr.std(ddof=1))
    if sd == 0:
        return None
    return float((value - arr.mean()) / sd)


def hurst_dfa(returns: np.ndarray, scales: Optional[Sequence[int]] = None) -> Optional[float]:
    """Hurst exponent via Detrended Fluctuation Analysis.

    DFA is used on purpose (matching research-terminal's rationale): naive R/S
    reads ~0.60 on a random walk, which produces false "trending" verdicts.
    """
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 128:
        return None
    y = np.cumsum(x - x.mean())
    if scales is None:
        scales = [n for n in (8, 16, 32, 64, 128) if n <= y.size // 2]
    if len(scales) < 3:
        return None

    fluctuations = []
    used_scales = []
    for n in scales:
        segments = y.size // n
        if segments < 2:
            continue
        rms = []
        for i in range(segments):
            seg = y[i * n : (i + 1) * n]
            t = np.arange(n, dtype=float)
            coeffs = np.polyfit(t, seg, 1)
            trend = np.polyval(coeffs, t)
            rms.append(float(np.sqrt(np.mean((seg - trend) ** 2))))
        f = float(np.sqrt(np.mean(np.square(rms))))
        if f > 0:
            fluctuations.append(f)
            used_scales.append(n)

    if len(fluctuations) < 3:
        return None
    slope = np.polyfit(np.log(used_scales), np.log(fluctuations), 1)[0]
    return float(slope)


def historical_percentile(value: float, sample: Sequence[float]) -> Optional[float]:
    """Percentile rank of ``value`` within ``sample`` (0-100)."""
    arr = np.asarray(sample, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    below = float(np.sum(arr <= value))
    return float(below / arr.size * 100.0)


# --- the economic model -------------------------------------------------------

@dataclass
class ModelComponent:
    name: str
    weight: float
    daily_drift: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "weight": round(self.weight, 4),
            "daily_drift": round(self.daily_drift, 6),
            "annualised_drift": round(self.daily_drift * TRADING_DAYS, 4),
            "rationale": self.rationale,
        }


@dataclass
class ForecastResult:
    index_code: str
    index_name: str
    as_of: str
    last_close: float
    observations: int
    horizon_days: int

    annualised_drift: float
    annualised_volatility: float
    max_drawdown: float
    hurst: Optional[float]
    valuation_z: Optional[float]
    valuation_percentile: Optional[float]
    regime: str

    components: List[ModelComponent] = field(default_factory=list)
    quantiles: Dict[str, List[float]] = field(default_factory=dict)
    dates: List[str] = field(default_factory=list)
    expected_band: Dict[str, float] = field(default_factory=dict)
    basis: List[str] = field(default_factory=list)
    limits: List[str] = field(default_factory=list)
    available: Dict[str, bool] = field(default_factory=dict)
    is_simulated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_code": self.index_code,
            "index_name": self.index_name,
            "as_of": self.as_of,
            "last_close": round(self.last_close, 4),
            "observations": self.observations,
            "horizon_days": self.horizon_days,
            "metrics": {
                "annualised_drift": round(self.annualised_drift, 4),
                "annualised_volatility": round(self.annualised_volatility, 4),
                "max_drawdown": round(self.max_drawdown, 4),
                "hurst": None if self.hurst is None else round(self.hurst, 4),
                "valuation_z": None if self.valuation_z is None else round(self.valuation_z, 4),
                "valuation_percentile": (
                    None if self.valuation_percentile is None else round(self.valuation_percentile, 2)
                ),
                "regime": self.regime,
            },
            "model": {
                "kind": "drift+mean_reversion",
                "components": [c.to_dict() for c in self.components],
                "blended_daily_drift": round(self._blended_daily_drift(), 6),
            },
            "projection": {
                "dates": self.dates,
                "quantiles": self.quantiles,
            },
            "expected_band": self.expected_band,
            "basis": self.basis,
            "limits": self.limits,
            "available": self.available,
            "is_simulated": self.is_simulated,
        }

    def _blended_daily_drift(self) -> float:
        total = sum(c.weight for c in self.components) or 1.0
        return sum(c.daily_drift * c.weight for c in self.components) / total


def _classify_regime(hurst: Optional[float], ann_drift: float, ann_vol: float) -> str:
    """Plain-language regime label derived from measurable inputs."""
    if hurst is None:
        return "unknown"
    if hurst > 0.55:
        base = "trending"
    elif hurst < 0.45:
        base = "mean_reverting"
    else:
        base = "random_walk"
    if ann_vol > 0.35:
        base += "_high_vol"
    return base


def _empirical_quantile_paths(
    returns: np.ndarray,
    last_close: float,
    horizon: int,
    daily_drift: float,
    n_paths: int = 2000,
    seed: Optional[int] = None,
) -> Tuple[Dict[str, List[float]], List[str], Dict[str, float]]:
    """Bootstrap forward paths from realised returns, anchored on the last close.

    Returns (quantiles, future_dates, expected_band). The drift is applied as a
    deterministic per-step adjustment on top of the *resampled* returns, so the
    band still reflects the true (fat-tailed) distribution of daily moves.
    """
    rng = np.random.default_rng(seed)
    if returns.size == 0:
        raise ForecastError("no_bars", "no returns to bootstrap")

    # Resample with replacement; subtract realised mean then add model drift so
    # the specified drift is the one actually projected.
    centred = returns - returns.mean()
    draws = rng.choice(centred, size=(n_paths, horizon), replace=True)
    draws = draws + daily_drift
    log_paths = np.cumsum(draws, axis=1)
    paths = last_close * np.exp(log_paths)

    quantile_levels = {"p10": 10, "p25": 25, "p50": 50, "p75": 75, "p90": 90}
    # Prepend the anchor point so charts start at the last close.
    out: Dict[str, List[float]] = {}
    for name, q in quantile_levels.items():
        series = np.percentile(paths, q, axis=0)
        out[name] = [round(last_close, 4)] + [round(float(v), 4) for v in series]

    dates = _future_trading_dates(horizon)
    band = {
        "median_return": round(float(np.median(paths[:, -1]) / last_close - 1.0), 4),
        "p10_return": round(float(np.percentile(paths[:, -1], 10) / last_close - 1.0), 4),
        "p90_return": round(float(np.percentile(paths[:, -1], 90) / last_close - 1.0), 4),
        "prob_up": round(float(np.mean(paths[:, -1] > last_close)), 4),
    }
    return out, dates, band


def _future_trading_dates(horizon: int) -> List[str]:
    """Approximate future trading dates (skips weekends; holidays unknown)."""
    dates: List[str] = []
    cursor = _date.today()
    while len(dates) < horizon:
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
    return dates


def build_forecast(
    index_code: str,
    index_name: str,
    closes: Sequence[float],
    dates: Sequence[str],
    *,
    lookback: int = DEFAULT_LOOKBACK,
    horizon: int = DEFAULT_HORIZON,
    valuation_series: Optional[Sequence[float]] = None,
) -> ForecastResult:
    """Assemble a full, honest forecast from a real closing series.

    Raises :class:`ForecastError` when the input is too thin to support any
    statistical claim.
    """
    if horizon <= 0:
        horizon = DEFAULT_HORIZON
    if horizon > MAX_HORIZON:
        horizon = MAX_HORIZON

    prices = np.asarray(closes, dtype=float)
    mask = np.isfinite(prices) & (prices > 0)
    prices = prices[mask]
    used_dates = [d for d, m in zip(dates, mask) if m]

    if prices.size < MIN_OBSERVATIONS:
        raise ForecastError(
            "insufficient_history",
            f"need >= {MIN_OBSERVATIONS} closes, got {int(prices.size)}",
        )

    window = prices[-lookback:] if prices.size > lookback else prices
    returns = to_log_returns(window)

    ann_drift = annualised_drift(returns)
    ann_vol = annualised_volatility(returns)
    mdd = max_drawdown(window)
    hurst = hurst_dfa(returns)
    last_close = float(window[-1])

    # Mean-reversion pull: distance of the latest close from its own moving
    # average, expressed in log-price standard deviations so the z-score is
    # dimensionless. Positive z -> stretched above trend -> mean-reverting drag.
    ma_window = min(120, window.size)
    log_window = np.log(window[-ma_window:])
    log_mean = float(np.mean(log_window))
    log_sd = float(np.std(log_window, ddof=1)) if log_window.size >= 2 else 0.0
    valuation_z: Optional[float] = None
    if log_sd > 0:
        valuation_z = (float(np.log(last_close)) - log_mean) / log_sd
    # Daily volatility in log-return units, used to scale the reversion pull.
    daily_vol = ann_vol / math.sqrt(TRADING_DAYS) if ann_vol > 0 else 0.0
    valuation_percentile = historical_percentile(last_close, window)

    # --- model components ----------------------------------------------------
    drift_component = ModelComponent(
        name="historical_drift",
        weight=0.6,
        daily_drift=ann_drift / TRADING_DAYS,
        rationale="近%s日对数收益的年化均值，代表样本内实际漂移。" % min(lookback, window.size),
    )

    # Mean reversion: pull the endpoint toward the long mean. Coefficient is
    # deliberately conservative (0.10) so the band, not the point, carries the
    # uncertainty.
    reversion_daily = 0.0
    reversion_rationale = "缺少波动率样本，未启用均值回归分量。"
    if valuation_z is not None and daily_vol > 0:
        # Clamp the stretch so a single outlier cannot run away, then pull a
        # fraction of it back per day. Units: log-return per day.
        z_clamped = max(-4.0, min(4.0, valuation_z))
        pull = -0.10 * z_clamped * daily_vol
        reversion_daily = pull
        direction = "向下" if z_clamped > 0 else "向上"
        reversion_rationale = (
            f"现价偏离自身120日均值 {z_clamped:+.2f}σ（对数价位），按 0.10 系数施加{direction}回调。"
        )
    reversion_component = ModelComponent(
        name="mean_reversion",
        weight=0.4,
        daily_drift=reversion_daily,
        rationale=reversion_rationale,
    )

    blended_daily = (drift_component.daily_drift * drift_component.weight +
                     reversion_component.daily_drift * reversion_component.weight) / (
        drift_component.weight + reversion_component.weight)
    # Final safety clamp: the projected daily drift may never exceed 3× the
    # realised daily volatility. Keeps a single outlier from producing an
    # absurd path while staying explicit about the bound.
    if daily_vol > 0:
        cap = 3.0 * daily_vol
        blended_daily = max(-cap, min(cap, blended_daily))

    quantiles, future_dates, band = _empirical_quantile_paths(
        returns, last_close, horizon, blended_daily
    )

    regime = _classify_regime(hurst, ann_drift, ann_vol)

    basis = [
        "样本：真实日线收盘价，取近%d个交易日。" % min(lookback, window.size),
        "收益：对数收益，年化按 252 交易日。",
        "分位带：对样本内日收益做有放回重采样 2000 条路径，保留厚尾，不假设正态。",
        "中位路径 = 历史漂移(权重0.6) + 均值回归(权重0.4) 的线性组合。",
    ]
    limits = [
        "不含盘中滑点、分红税、交易成本与涨跌停限制。",
        "未来交易日按“跳过周末”近似，未考虑法定节假日。",
        "分位带是历史重采样的经验区间，不是概率保证，也不构成投资建议。",
        "日漂移已钳制在 ±3 倍样本日波动以内，避免单点异常放大路径。",
    ]
    if valuation_series is not None:
        basis.append("估值序列已提供，用于辅助判定，不直接进入价格路径。")

    return ForecastResult(
        index_code=index_code,
        index_name=index_name,
        as_of=str(used_dates[-1]) if used_dates else "",
        last_close=last_close,
        observations=int(window.size),
        horizon_days=horizon,
        annualised_drift=ann_drift,
        annualised_volatility=ann_vol,
        max_drawdown=mdd,
        hurst=hurst,
        valuation_z=valuation_z,
        valuation_percentile=valuation_percentile,
        regime=regime,
        components=[drift_component, reversion_component],
        quantiles=quantiles,
        dates=future_dates,
        expected_band=band,
        basis=basis,
        limits=limits,
        available={"price_series": True},
        is_simulated=False,
    )
