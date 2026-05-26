"""
Quantitative Engine - Phase Space Trajectory Analysis.

Implements mathematical calculations for market crowding rotation analysis
using phase space dynamics (position, velocity, acceleration).

Mathematical Framework:
-----------------------
Phase Space Vector: (crowding_score, pe_percentile)
- Position: (x, y) at time T
- Velocity: d(crowding_score)/dt
- Acceleration: d²(crowding_score)/dt²

Trajectory Vector (T₀ → T₁):
- Start point: (crowding_T0, pe_T0)
- End point: (crowding_T1, pe_T1)
- Arrow direction: θ = atan2(Δpe, Δcrowding)
- Magnitude: |v| = sqrt(Δcrowding² + Δpe²)

Rotation Detection:
- Angular velocity: ω = dθ/dt
- Regime change: |ω| > threshold
- Classification: clockwise (improving), counter-clockwise (deteriorating)
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta


def calculate_phase_space_position(
    crowding_score: float,
    pe_percentile: float,
) -> Tuple[float, float]:
    """
    Calculate phase space position vector.
    
    Args:
        crowding_score: Market crowding score (0-100)
        pe_percentile: PE ratio percentile (0-100)
    
    Returns:
        Tuple[float, float]: (x, y) position in phase space
    """
    return (float(crowding_score), float(pe_percentile))


def calculate_trajectory_vector(
    t0_crowding: float,
    t0_pe: float,
    t1_crowding: float,
    t1_pe: float,
) -> Dict[str, float]:
    """
    Calculate trajectory vector from T₀ to T₁.
    
    Mathematical Formula:
        Δcrowding = crowding_T1 - crowding_T0
        Δpe = pe_T1 - pe_T0
        θ = atan2(Δpe, Δcrowding)  # Direction in radians
        |v| = sqrt(Δcrowding² + Δpe²)  # Magnitude
    
    Args:
        t0_crowding: Crowding score at T₀
        t0_pe: PE percentile at T₀
        t1_crowding: Crowding score at T₁
        t1_pe: PE percentile at T₁
    
    Returns:
        Dict with delta_crowding, delta_pe, direction (radians), magnitude
    """
    delta_crowding = t1_crowding - t0_crowding
    delta_pe = t1_pe - t0_pe
    
    # Direction: atan2(y, x) where y=Δpe, x=Δcrowding
    direction = np.arctan2(delta_pe, delta_crowding)
    
    # Magnitude: Euclidean distance
    magnitude = np.sqrt(delta_crowding**2 + delta_pe**2)
    
    return {
        "delta_crowding": float(delta_crowding),
        "delta_pe": float(delta_pe),
        "direction_rad": float(direction),
        "direction_deg": float(np.degrees(direction)),
        "magnitude": float(magnitude),
    }


def calculate_velocity(
    crowding_scores: List[float],
    time_points: List[str],
    window_days: int = 20,
) -> List[float]:
    """
    Calculate velocity (first derivative) of crowding score over time.
    
    Mathematical Formula:
        v = d(crowding)/dt ≈ Δcrowding / Δt
    
    Uses finite difference approximation with interpolation for missing data.
    
    Args:
        crowding_scores: List of crowding scores ordered by time
        time_points: List of date strings "YYYY-MM-DD"
        window_days: Time window for velocity calculation (default 20 trading days)
    
    Returns:
        List of velocity values (same length as input)
    """
    if len(crowding_scores) < 2:
        return [0.0] * len(crowding_scores)
    
    velocities = []
    n = len(crowding_scores)
    
    # Parse dates
    dates = [datetime.strptime(t, "%Y-%m-%d") for t in time_points]
    
    for i in range(n):
        if i == 0:
            # Forward difference for first point
            if n > 1:
                dt = (dates[1] - dates[0]).days
                if dt > 0:
                    v = (crowding_scores[1] - crowding_scores[0]) / dt
                else:
                    v = 0.0
            else:
                v = 0.0
        elif i == n - 1:
            # Backward difference for last point
            dt = (dates[i] - dates[i-1]).days
            if dt > 0:
                v = (crowding_scores[i] - crowding_scores[i-1]) / dt
            else:
                v = 0.0
        else:
            # Central difference for interior points
            dt_forward = (dates[i+1] - dates[i]).days
            dt_backward = (dates[i] - dates[i-1]).days
            dt_total = dt_forward + dt_backward
            
            if dt_total > 0:
                v = (crowding_scores[i+1] - crowding_scores[i-1]) / dt_total
            else:
                v = 0.0
        
        velocities.append(float(v))
    
    return velocities


def calculate_acceleration(
    velocities: List[float],
    time_points: List[str],
) -> List[float]:
    """
    Calculate acceleration (second derivative) of crowding score.
    
    Mathematical Formula:
        a = d²(crowding)/dt² = dv/dt
    
    Args:
        velocities: List of velocity values from calculate_velocity()
        time_points: List of date strings "YYYY-MM-DD"
    
    Returns:
        List of acceleration values
    """
    if len(velocities) < 2:
        return [0.0] * len(velocities)
    
    accelerations = []
    n = len(velocities)
    dates = [datetime.strptime(t, "%Y-%m-%d") for t in time_points]
    
    for i in range(n):
        if i == 0:
            dt = (dates[1] - dates[0]).days
            if dt > 0:
                a = (velocities[1] - velocities[0]) / dt
            else:
                a = 0.0
        elif i == n - 1:
            dt = (dates[i] - dates[i-1]).days
            if dt > 0:
                a = (velocities[i] - velocities[i-1]) / dt
            else:
                a = 0.0
        else:
            dt_forward = (dates[i+1] - dates[i]).days
            dt_backward = (dates[i] - dates[i-1]).days
            dt_total = dt_forward + dt_backward
            
            if dt_total > 0:
                a = (velocities[i+1] - velocities[i-1]) / dt_total
            else:
                a = 0.0
        
        accelerations.append(float(a))
    
    return accelerations


def calculate_angular_velocity(
    trajectory_vectors: List[Dict[str, float]],
    time_points: List[str],
) -> List[float]:
    """
    Calculate angular velocity (rate of direction change).
    
    Mathematical Formula:
        ω = dθ/dt
    
    Args:
        trajectory_vectors: List of trajectory vectors with 'direction_rad'
        time_points: List of date strings
    
    Returns:
        List of angular velocity values (radians per day)
    """
    if len(trajectory_vectors) < 2:
        return [0.0] * len(trajectory_vectors)
    
    angular_velocities = []
    n = len(trajectory_vectors)
    dates = [datetime.strptime(t, "%Y-%m-%d") for t in time_points]
    
    for i in range(n):
        if i == 0:
            dt = (dates[1] - dates[0]).days
            if dt > 0:
                d_theta = trajectory_vectors[1]["direction_rad"] - trajectory_vectors[0]["direction_rad"]
                # Normalize to [-π, π]
                d_theta = np.arctan2(np.sin(d_theta), np.cos(d_theta))
                omega = d_theta / dt
            else:
                omega = 0.0
        elif i == n - 1:
            dt = (dates[i] - dates[i-1]).days
            if dt > 0:
                d_theta = trajectory_vectors[i]["direction_rad"] - trajectory_vectors[i-1]["direction_rad"]
                d_theta = np.arctan2(np.sin(d_theta), np.cos(d_theta))
                omega = d_theta / dt
            else:
                omega = 0.0
        else:
            dt_forward = (dates[i+1] - dates[i]).days
            dt_backward = (dates[i] - dates[i-1]).days
            dt_total = dt_forward + dt_backward
            
            if dt_total > 0:
                d_theta = trajectory_vectors[i+1]["direction_rad"] - trajectory_vectors[i-1]["direction_rad"]
                d_theta = np.arctan2(np.sin(d_theta), np.cos(d_theta))
                omega = d_theta / dt_total
            else:
                omega = 0.0
        
        angular_velocities.append(float(omega))
    
    return angular_velocities


def classify_rotation(
    direction_rad: float,
    delta_crowding: float,
    delta_pe: float,
) -> str:
    """
    Classify rotation direction based on trajectory.
    
    Classification Rules:
        - Clockwise (improving): PE decreasing while crowding stable/increasing
        - Counter-clockwise (deteriorating): PE increasing while crowding stable/decreasing
        - Neutral: Minimal movement
    
    Args:
        direction_rad: Direction angle in radians
        delta_crowding: Change in crowding score
        delta_pe: Change in PE percentile
    
    Returns:
        "clockwise", "counter_clockwise", or "neutral"
    """
    # Threshold for significant movement
    magnitude = np.sqrt(delta_crowding**2 + delta_pe**2)
    
    if magnitude < 5.0:  # Minimal movement threshold
        return "neutral"
    
    # Clockwise: PE decreasing (improving valuation)
    # In phase space: moving down (negative Δpe) or right-down
    if delta_pe < -5.0 and delta_crowding >= -5.0:
        return "clockwise"
    
    # Counter-clockwise: PE increasing (deteriorating valuation)
    # In phase space: moving up (positive Δpe) or left-up
    if delta_pe > 5.0 and delta_crowding <= 5.0:
        return "counter_clockwise"
    
    # Mixed movement
    if delta_crowding > 5.0 and delta_pe > 5.0:
        return "expansion"  # Both increasing
    elif delta_crowding < -5.0 and delta_pe < -5.0:
        return "contraction"  # Both decreasing
    
    return "neutral"


def detect_regime_change(
    angular_velocities: List[float],
    threshold: float = 0.05,
) -> Tuple[bool, List[int]]:
    """
    Detect regime changes based on angular velocity spikes.
    
    Mathematical Formula:
        Regime change when |ω| > threshold
    
    Args:
        angular_velocities: List of angular velocity values
        threshold: Threshold for regime change detection (radians/day)
    
    Returns:
        Tuple of (has_regime_change, list of change indices)
    """
    change_indices = []
    
    for i, omega in enumerate(angular_velocities):
        if abs(omega) > threshold:
            change_indices.append(i)
    
    has_change = len(change_indices) > 0
    
    return (has_change, change_indices)


def interpolate_missing_data(
    data_points: List[Dict[str, Optional[float]]],
    time_points: List[str],
) -> List[Dict[str, float]]:
    """
    Interpolate missing data points using linear interpolation.
    
    Args:
        data_points: List of dicts with 'crowding_score' and 'pe_percentile'
        time_points: List of date strings
    
    Returns:
        List with interpolated values for missing data
    """
    if len(data_points) == 0:
        return []
    
    # Find indices with missing data
    interpolated = []
    n = len(data_points)
    
    for i, point in enumerate(data_points):
        if point.get("crowding_score") is None or point.get("pe_percentile") is None:
            # Find nearest valid neighbors
            prev_idx = None
            next_idx = None
            
            for j in range(i-1, -1, -1):
                if data_points[j].get("crowding_score") is not None:
                    prev_idx = j
                    break
            
            for j in range(i+1, n):
                if data_points[j].get("crowding_score") is not None:
                    next_idx = j
                    break
            
            # Interpolate
            if prev_idx is not None and next_idx is not None:
                # Linear interpolation
                alpha = (i - prev_idx) / (next_idx - prev_idx)
                interpolated_point = {
                    "crowding_score": data_points[prev_idx]["crowding_score"] * (1 - alpha) + 
                                     data_points[next_idx]["crowding_score"] * alpha,
                    "pe_percentile": data_points[prev_idx]["pe_percentile"] * (1 - alpha) + 
                                    data_points[next_idx]["pe_percentile"] * alpha,
                }
            elif prev_idx is not None:
                # Use previous value
                interpolated_point = {
                    "crowding_score": data_points[prev_idx]["crowding_score"],
                    "pe_percentile": data_points[prev_idx]["pe_percentile"],
                }
            elif next_idx is not None:
                # Use next value
                interpolated_point = {
                    "crowding_score": data_points[next_idx]["crowding_score"],
                    "pe_percentile": data_points[next_idx]["pe_percentile"],
                }
            else:
                # No valid data, use defaults
                interpolated_point = {
                    "crowding_score": 50.0,
                    "pe_percentile": 50.0,
                }
            
            interpolated.append(interpolated_point)
        else:
            interpolated.append(point)
    
    return interpolated


def calculate_phase_space_trajectory(
    history_data: List[Dict],
    t0_date: str,
    t1_date: str,
) -> Dict:
    """
    Main function: Calculate complete phase space trajectory for an asset.
    
    Args:
        history_data: List of historical records with fields:
            - trade_date: str
            - crowding_score: float
            - pe_percentile: float
        t0_date: Start date "YYYY-MM-DD"
        t1_date: End date "YYYY-MM-DD"
    
    Returns:
        Dict with trajectory vector, velocity, rotation classification, regime change
    """
    # Validate date range
    t0 = datetime.strptime(t0_date, "%Y-%m-%d")
    t1 = datetime.strptime(t1_date, "%Y-%m-%d")
    
    if t1 <= t0:
        raise ValueError(f"End date {t1_date} must be after start date {t0_date}")
    
    # Sort by date
    sorted_data = sorted(history_data, key=lambda x: x["trade_date"])
    
    # Filter data within date range
    filtered_data = [
        d for d in sorted_data
        if t0_date <= d["trade_date"] <= t1_date
    ]
    
    if len(filtered_data) < 2:
        raise ValueError(f"Insufficient data points between {t0_date} and {t1_date}")
    
    # Interpolate missing data
    data_for_interpolation = []
    for d in filtered_data:
        data_for_interpolation.append({
            "crowding_score": d.get("crowding_score"),
            "pe_percentile": d.get("pe_percentile"),
        })
    
    interpolated = interpolate_missing_data(
        data_for_interpolation,
        [d["trade_date"] for d in filtered_data]
    )
    
    # Extract time series
    time_points = [d["trade_date"] for d in filtered_data]
    crowding_scores = [p["crowding_score"] for p in interpolated]
    pe_percentiles = [p["pe_percentile"] for p in interpolated]
    
    # Calculate trajectory vector (T₀ → T₁)
    t0_crowding = crowding_scores[0]
    t0_pe = pe_percentiles[0]
    t1_crowding = crowding_scores[-1]
    t1_pe = pe_percentiles[-1]
    
    trajectory = calculate_trajectory_vector(
        t0_crowding, t0_pe, t1_crowding, t1_pe
    )
    
    # Calculate velocity
    velocities = calculate_velocity(crowding_scores, time_points)
    avg_velocity = float(np.mean(velocities)) if velocities else 0.0
    
    # Calculate acceleration
    accelerations = calculate_acceleration(velocities, time_points)
    avg_acceleration = float(np.mean(accelerations)) if accelerations else 0.0
    
    # Classify rotation
    rotation = classify_rotation(
        trajectory["direction_rad"],
        trajectory["delta_crowding"],
        trajectory["delta_pe"]
    )
    
    # Calculate angular velocity for regime change detection
    # Build trajectory vectors for each time step
    step_vectors = []
    for i in range(len(crowding_scores) - 1):
        vec = calculate_trajectory_vector(
            crowding_scores[i], pe_percentiles[i],
            crowding_scores[i+1], pe_percentiles[i+1]
        )
        step_vectors.append(vec)
    
    if step_vectors:
        angular_velocities = calculate_angular_velocity(
            step_vectors, time_points[:-1]
        )
        has_regime_change, change_indices = detect_regime_change(angular_velocities)
    else:
        has_regime_change = False
        change_indices = []
    
    return {
        "trajectory": trajectory,
        "velocity": avg_velocity,
        "acceleration": avg_acceleration,
        "rotation": rotation,
        "regime_change": has_regime_change,
        "regime_change_indices": change_indices,
        "start": {
            "x": t0_crowding,
            "y": t0_pe,
            "date": t0_date,
        },
        "end": {
            "x": t1_crowding,
            "y": t1_pe,
            "date": t1_date,
        },
    }


def build_echarts_trajectory_data(
    trajectories: List[Dict],
) -> Dict:
    """
    Build ECharts-compatible data structure for trajectory visualization.
    
    Args:
        trajectories: List of trajectory results from calculate_phase_space_trajectory()
    
    Returns:
        Dict with ECharts series data
    """
    vectors = []
    
    for traj in trajectories:
        vectors.append({
            "asset": traj.get("asset_code", "Unknown"),
            "start": traj["start"],
            "end": traj["end"],
            "velocity": traj["velocity"],
            "rotation": traj["rotation"],
            "magnitude": traj["trajectory"]["magnitude"],
            "direction_deg": traj["trajectory"]["direction_deg"],
        })
    
    # Detect overall regime change
    regime_changes = [t for t in trajectories if t.get("regime_change", False)]
    
    return {
        "vectors": vectors,
        "regime_change": len(regime_changes) > 0,
        "regime_change_count": len(regime_changes),
    }
