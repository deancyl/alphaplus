"""
Stochastic Process Simulators for Graceful Degradation.

Implements GBM (Geometric Brownian Motion) and O-U (Ornstein-Uhlenbeck) processes
for generating fallback data when AkShare API fails.

Mathematical Framework:
-----------------------
GBM (for price/yield time series):
    S_t = S_{t-1} * exp((mu - sigma^2/2)*dt + sigma*epsilon*sqrt(dt))
    where epsilon ~ N(0,1)

O-U (for mean-reverting indicators):
    dx_t = kappa*(theta - x_t)*dt + sigma*dW_t
    where theta is the long-term mean, kappa is mean reversion speed

Performance Target: <10ms for 1000 paths, 252 steps
"""
import numpy as np
from typing import Optional, Tuple, Dict
import sqlite3
from pathlib import Path

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range


@jit(nopython=True, cache=True, fastmath=True)
def _simulate_ou_paths(X0: float, theta: float, kappa: float, sigma: float,
                        dt: float, N: int, n_paths: int, dW: np.ndarray) -> np.ndarray:
    paths = np.zeros((n_paths, N + 1))
    paths[:, 0] = X0
    
    for i in range(n_paths):
        for t in range(1, N + 1):
            drift = kappa * (theta - paths[i, t-1]) * dt
            diffusion = sigma * dW[i, t-1]
            paths[i, t] = paths[i, t-1] + drift + diffusion
    
    return paths


@jit(nopython=True, cache=True, fastmath=True)
def _simulate_gbm_paths(S0: float, drift: float, sigma_sqrt_dt: float,
                         N: int, n_paths: int, epsilon: np.ndarray) -> np.ndarray:
    paths = np.zeros((n_paths, N + 1))
    paths[:, 0] = S0
    
    log_returns = drift + sigma_sqrt_dt * epsilon
    
    for i in range(n_paths):
        cumulative = 0.0
        for t in range(1, N + 1):
            cumulative += log_returns[i, t-1]
            paths[i, t] = S0 * np.exp(cumulative)
    
    return paths


class GBMSimulator:
    """
    Geometric Brownian Motion Simulator.
    
    Used for simulating price/yield time series with drift and volatility.
    
    Formula:
        S_t = S_{t-1} * exp((mu - sigma^2/2)*dt + sigma*epsilon*sqrt(dt))
    
    Parameters:
        S0: Initial price/value
        mu: Drift coefficient (annualized)
        sigma: Volatility coefficient (annualized)
        T: Time horizon (in years)
        N: Number of time steps
        n_paths: Number of simulation paths
    """
    
    def __init__(
        self,
        S0: float,
        mu: float,
        sigma: float,
        T: float = 1.0,
        N: int = 252,
        n_paths: int = 1000,
    ):
        """
        Initialize GBM simulator.
        
        Args:
            S0: Initial price/value
            mu: Drift coefficient (annualized, e.g., 0.08 for 8%)
            sigma: Volatility coefficient (annualized, e.g., 0.20 for 20%)
            T: Time horizon in years (default 1.0)
            N: Number of time steps (default 252 for trading days)
            n_paths: Number of simulation paths (default 1000)
        """
        self.S0 = S0
        self.mu = mu
        self.sigma = sigma
        self.T = T
        self.N = N
        self.n_paths = n_paths
        self.dt = T / N
        
        # Storage for last simulation
        self._last_paths: Optional[np.ndarray] = None
    
    def simulate(self, seed: Optional[int] = None) -> np.ndarray:
        """
        Simulate GBM paths.
        
        Returns:
            np.ndarray of shape (n_paths, N+1) where:
            - First column is S0
            - Each row is one path
            - Each column is one time step
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Generate all random numbers at once for efficiency
        epsilon = np.random.standard_normal((self.n_paths, self.N))
        
        # Pre-compute drift and diffusion coefficients
        drift_per_step = (self.mu - 0.5 * self.sigma**2) * self.dt
        sigma_sqrt_dt = self.sigma * np.sqrt(self.dt)
        
        # Use JIT-compiled function for performance
        paths = _simulate_gbm_paths(
            self.S0, drift_per_step, sigma_sqrt_dt, self.N, self.n_paths, epsilon
        )
        
        self._last_paths = paths
        return paths
    
    def check_mean(self, paths: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Validate mean of simulated paths against theoretical expectation.
        
        Theoretical mean of GBM at time t:
            E[S_t] = S0 * exp(mu * t)
        
        Args:
            paths: Simulated paths (uses last simulation if None)
        
        Returns:
            Dict with theoretical_mean, empirical_mean, relative_error
        """
        paths = paths if paths is not None else self._last_paths
        if paths is None:
            raise ValueError("No paths available. Run simulate() first.")
        
        # Theoretical mean at final time
        theoretical_mean = self.S0 * np.exp(self.mu * self.T)
        
        # Empirical mean at final time
        empirical_mean = np.mean(paths[:, -1])
        
        # Relative error
        relative_error = abs(empirical_mean - theoretical_mean) / theoretical_mean
        
        return {
            "theoretical_mean": float(theoretical_mean),
            "empirical_mean": float(empirical_mean),
            "relative_error": float(relative_error),
            "tolerance_met": relative_error < 0.05,  # 5% tolerance
        }
    
    def check_variance(self, paths: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Validate variance of simulated paths against theoretical expectation.
        
        Theoretical variance of GBM at time t:
            Var[S_t] = S0^2 * exp(2*mu*t) * (exp(sigma^2*t) - 1)
        
        Args:
            paths: Simulated paths (uses last simulation if None)
        
        Returns:
            Dict with theoretical_var, empirical_var, relative_error
        """
        paths = paths if paths is not None else self._last_paths
        if paths is None:
            raise ValueError("No paths available. Run simulate() first.")
        
        # Theoretical variance at final time
        theoretical_var = (
            self.S0**2 
            * np.exp(2 * self.mu * self.T) 
            * (np.exp(self.sigma**2 * self.T) - 1)
        )
        
        # Empirical variance at final time
        empirical_var = np.var(paths[:, -1], ddof=1)
        
        # Relative error
        relative_error = abs(empirical_var - theoretical_var) / theoretical_var
        
        return {
            "theoretical_variance": float(theoretical_var),
            "empirical_variance": float(empirical_var),
            "relative_error": float(relative_error),
            "tolerance_met": relative_error < 0.10,  # 10% tolerance for variance
        }


class OUSimulator:
    """
    Ornstein-Uhlenbeck Process Simulator.
    
    Used for simulating mean-reverting indicators (fear-greed, crowding, percentile).
    
    Formula:
        dx_t = kappa*(theta - x_t)*dt + sigma*dW_t
    
    Parameters:
        X0: Initial value
        theta: Long-term mean level
        kappa: Mean reversion speed (higher = faster reversion)
        sigma: Volatility coefficient
        T: Time horizon (in years)
        N: Number of time steps
        n_paths: Number of simulation paths
    """
    
    def __init__(
        self,
        X0: float,
        theta: float,
        kappa: float,
        sigma: float,
        T: float = 1.0,
        N: int = 252,
        n_paths: int = 1000,
    ):
        """
        Initialize O-U simulator.
        
        Args:
            X0: Initial value
            theta: Long-term mean level (e.g., 50 for fear-greed index)
            kappa: Mean reversion speed (e.g., 0.15 for crowding, 0.05 for style ratio)
            sigma: Volatility coefficient
            T: Time horizon in years (default 1.0)
            N: Number of time steps (default 252 for trading days)
            n_paths: Number of simulation paths (default 1000)
        """
        self.X0 = X0
        self.theta = theta
        self.kappa = kappa
        self.sigma = sigma
        self.T = T
        self.N = N
        self.n_paths = n_paths
        self.dt = T / N
        
        # Storage for last simulation
        self._last_paths: Optional[np.ndarray] = None
    
    def simulate(self, seed: Optional[int] = None) -> np.ndarray:
        """
        Simulate O-U paths using Euler-Maruyama discretization.
        
        Returns:
            np.ndarray of shape (n_paths, N+1) where:
            - First column is X0
            - Each row is one path
            - Each column is one time step
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Generate all random numbers at once
        dW = np.random.standard_normal((self.n_paths, self.N)) * np.sqrt(self.dt)
        
        # Use JIT-compiled function for performance
        paths = _simulate_ou_paths(
            self.X0, self.theta, self.kappa, self.sigma,
            self.dt, self.N, self.n_paths, dW
        )
        
        self._last_paths = paths
        return paths
    
    def check_mean(self, paths: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Validate mean of simulated paths against theoretical expectation.
        
        Theoretical mean of O-U at time t:
            E[X_t] = theta + (X0 - theta)*exp(-kappa*t)
        
        As t -> infinity, E[X_t] -> theta
        
        Args:
            paths: Simulated paths (uses last simulation if None)
        
        Returns:
            Dict with theoretical_mean, empirical_mean, relative_error
        """
        paths = paths if paths is not None else self._last_paths
        if paths is None:
            raise ValueError("No paths available. Run simulate() first.")
        
        # Theoretical mean at final time
        theoretical_mean = (
            self.theta 
            + (self.X0 - self.theta) * np.exp(-self.kappa * self.T)
        )
        
        # Empirical mean at final time
        empirical_mean = np.mean(paths[:, -1])
        
        # Relative error (use absolute difference for bounded indicators)
        abs_diff = abs(empirical_mean - theoretical_mean)
        
        return {
            "theoretical_mean": float(theoretical_mean),
            "empirical_mean": float(empirical_mean),
            "absolute_error": float(abs_diff),
            "tolerance_met": abs_diff < 5.0,  # 5 points tolerance for bounded indicators
        }
    
    def check_variance(self, paths: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Validate variance of simulated paths against theoretical expectation.
        
        Theoretical variance of O-U at time t:
            Var[X_t] = sigma^2/(2*kappa) * (1 - exp(-2*kappa*t))
        
        As t -> infinity, Var[X_t] -> sigma^2/(2*kappa)
        
        Args:
            paths: Simulated paths (uses last simulation if None)
        
        Returns:
            Dict with theoretical_var, empirical_var, relative_error
        """
        paths = paths if paths is not None else self._last_paths
        if paths is None:
            raise ValueError("No paths available. Run simulate() first.")
        
        # Theoretical variance at final time
        theoretical_var = (
            self.sigma**2 / (2 * self.kappa) 
            * (1 - np.exp(-2 * self.kappa * self.T))
        )
        
        # Empirical variance at final time
        empirical_var = np.var(paths[:, -1], ddof=1)
        
        # Relative error
        relative_error = abs(empirical_var - theoretical_var) / theoretical_var
        
        return {
            "theoretical_variance": float(theoretical_var),
            "empirical_variance": float(empirical_var),
            "relative_error": float(relative_error),
            "tolerance_met": relative_error < 0.15,  # 15% tolerance for variance
        }
    
    def check_mean_reversion(self, paths: Optional[np.ndarray] = None) -> Dict[str, float | bool]:
        """
        Validate mean reversion property.
        
        Check if paths starting away from theta converge toward theta.
        
        Args:
            paths: Simulated paths (uses last simulation if None)
        
        Returns:
            Dict with convergence metrics
        """
        paths = paths if paths is not None else self._last_paths
        if paths is None:
            raise ValueError("No paths available. Run simulate() first.")
        
        # Calculate average distance from theta over time
        distances = np.abs(paths - self.theta)
        avg_distance_start = np.mean(distances[:, 0])
        avg_distance_end = np.mean(distances[:, -1])
        
        # Check if distance decreased (mean reversion)
        reversion_ratio = avg_distance_end / avg_distance_start if avg_distance_start > 0 else 1.0
        
        return {
            "initial_distance_from_theta": float(avg_distance_start),
            "final_distance_from_theta": float(avg_distance_end),
            "reversion_ratio": float(reversion_ratio),
            "mean_reversion_observed": bool(reversion_ratio < 1.0),
        }


def simulate_from_history(
    db_path: str,
    table_name: str,
    value_column: str,
    date_column: str = "trade_date",
    n_days: int = 30,
    n_paths: int = 100,
    process_type: str = "ou",
) -> np.ndarray:
    """
    Generate simulated continuation from historical data in SQLite.
    
    This is the degradation helper that reads last known values and generates
    consistent fallback data when AkShare API fails.
    
    Args:
        db_path: Path to SQLite database
        table_name: Table name containing historical data
        value_column: Column name for the value to simulate
        date_column: Column name for date (default "trade_date")
        n_days: Number of days to simulate (default 30)
        n_paths: Number of simulation paths (default 100)
        process_type: "gbm" for price/yield, "ou" for mean-reverting (default "ou")
    
    Returns:
        np.ndarray of shape (n_paths, n_days+1) with simulated continuation
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get last known values
    query = f"""
        SELECT {date_column}, {value_column}
        FROM {table_name}
        ORDER BY {date_column} DESC
        LIMIT 60
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 10:
        raise ValueError(f"Insufficient historical data: {len(rows)} rows")
    
    # Extract values (most recent first, reverse to chronological)
    values = np.array([row[1] for row in reversed(rows)])
    
    # Calculate parameters from history
    X0 = values[-1]  # Last known value
    theta = float(np.mean(values))  # Historical mean
    sigma = float(np.std(values, ddof=1))  # Historical volatility
    
    if process_type == "gbm":
        # Calculate drift from historical returns
        returns = np.diff(np.log(values[values > 0])) if np.all(values > 0) else np.diff(values) / values[:-1]
        mu = float(np.mean(returns) * 252)  # Annualized drift
        sigma_annual = sigma * np.sqrt(252)  # Annualized volatility
        
        simulator = GBMSimulator(
            S0=X0,
            mu=mu,
            sigma=sigma_annual,
            T=n_days / 252,
            N=n_days,
            n_paths=n_paths,
        )
    else:  # "ou"
        # Estimate kappa from autocorrelation
        # For O-U: autocorr(t) = exp(-kappa*t)
        # Use lag-1 autocorrelation: kappa ≈ -ln(autocorr(1))
        if len(values) > 1:
            autocorr = np.corrcoef(values[:-1], values[1:])[0, 1]
            kappa = -np.log(max(autocorr, 0.01))  # Prevent log(0)
            kappa = min(max(kappa, 0.01), 10.0)  # Bound kappa to reasonable range
        else:
            kappa = 0.15  # Default for crowding
        
        simulator = OUSimulator(
            X0=X0,
            theta=theta,
            kappa=kappa,
            sigma=sigma,
            T=n_days / 252,
            N=n_days,
            n_paths=n_paths,
        )
    
    return simulator.simulate()


# Convenience functions for common use cases
def simulate_price_fallback(
    last_price: float,
    mu: float = 0.08,
    sigma: float = 0.20,
    n_days: int = 30,
    n_paths: int = 100,
) -> np.ndarray:
    """
    Simulate price paths for fallback when market data API fails.
    
    Args:
        last_price: Last known price
        mu: Annualized drift (default 8%)
        sigma: Annualized volatility (default 20%)
        n_days: Number of days to simulate
        n_paths: Number of paths
    
    Returns:
        np.ndarray of shape (n_paths, n_days+1)
    """
    simulator = GBMSimulator(
        S0=last_price,
        mu=mu,
        sigma=sigma,
        T=n_days / 252,
        N=n_days,
        n_paths=n_paths,
    )
    return simulator.simulate()


def simulate_indicator_fallback(
    last_value: float,
    indicator_type: str = "fear_greed",
    n_days: int = 30,
    n_paths: int = 100,
) -> np.ndarray:
    """
    Simulate indicator paths for fallback when analytics API fails.
    
    Args:
        last_value: Last known indicator value
        indicator_type: "fear_greed", "crowding", or "percentile"
        n_days: Number of days to simulate
        n_paths: Number of paths
    
    Returns:
        np.ndarray of shape (n_paths, n_days+1)
    """
    # Default parameters based on indicator type
    params = {
        "fear_greed": {"theta": 50.0, "kappa": 0.10, "sigma": 15.0},
        "crowding": {"theta": 50.0, "kappa": 0.15, "sigma": 10.0},
        "percentile": {"theta": 50.0, "kappa": 0.05, "sigma": 20.0},
    }
    
    p = params.get(indicator_type, params["fear_greed"])
    
    simulator = OUSimulator(
        X0=last_value,
        theta=p["theta"],
        kappa=p["kappa"],
        sigma=p["sigma"],
        T=n_days / 252,
        N=n_days,
        n_paths=n_paths,
    )
    return simulator.simulate()


# Warm up JIT compilation at module import time
if NUMBA_AVAILABLE:
    _simulate_gbm_paths(100.0, 0.0001, 0.01, 252, 10, np.random.standard_normal((10, 252)))
    _simulate_ou_paths(50.0, 50.0, 0.15, 10.0, 0.004, 252, 10, np.random.standard_normal((10, 252)) * 0.063)
