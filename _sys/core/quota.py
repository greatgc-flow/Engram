import time
import math
from datetime import datetime

def get_remaining_seconds(reset_in_seconds=None, resets_at_iso=None, now_ts=None):
    """Normalize various expiry formats to remaining seconds."""
    if reset_in_seconds is not None:
        return max(0.0, float(reset_in_seconds))
    if not resets_at_iso:
        return None
    
    if now_ts is None:
        now_ts = time.time()
        
    if isinstance(resets_at_iso, (int, float)):
        # Treated as unix timestamp (seconds or milliseconds)
        ts = float(resets_at_iso)
        if ts > 2e10:
            ts /= 1000.0
        return max(0.0, ts - now_ts)
        
    # Python <3.11 fromisoformat compatibility for 'Z'
    iso_str = str(resets_at_iso).replace("Z", "+00:00")
    try:
        reset_ts = datetime.fromisoformat(iso_str).timestamp()
        return max(0.0, reset_ts - now_ts)
    except Exception:
        return None

def calculate_pacing(used_frac: float, remaining_seconds: float, window_hours: float) -> dict:
    """
    Calculate pacing ratio.
    Returns: {"ratio": float, "status": "safe"|"warn"|"danger"|"unknown", "indicator": str}
    """
    if used_frac <= 0.0:
        return {"ratio": 0.0, "status": "safe", "indicator": "🟢"}
        
    if remaining_seconds is None or remaining_seconds < 0:
        return {"ratio": 0.0, "status": "unknown", "indicator": ""}

    if window_hours <= 0.0:
        return {"ratio": 0.0, "status": "unknown", "indicator": ""}

    total_seconds = window_hours * 3600.0
    elapsed_seconds = max(0.0, total_seconds - remaining_seconds)
    elapsed_frac = elapsed_seconds / total_seconds
    
    # Spike prevention at the start of a window
    smoothed_elapsed = max(0.05, elapsed_frac)
        
    pacing_ratio = used_frac / smoothed_elapsed
    
    if pacing_ratio > 1.0:
        status, indicator = "danger", "🔴"
    elif pacing_ratio >= 0.8:
        status, indicator = "warn", "🟡"
    else:
        status, indicator = "safe", "🟢"
        
    return {"ratio": round(pacing_ratio, 2), "status": status, "indicator": indicator, "elapsed_frac": elapsed_frac}


def time_to_exhaustion(used_frac, pacing_ratio, window_hours):
    """Return projected hours until a quota bucket reaches 100%.

    The projection uses only measured bucket inputs. ``None`` means the
    projection is absent; a zero measured burn rate means exhaustion is
    infinitely far away. Values are intentionally not rounded here so callers
    can compare the projection with the bucket's own reset precisely.
    """
    values = (used_frac, pacing_ratio, window_hours)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        return None
    used_frac, pacing_ratio, window_hours = map(float, values)
    if not all(math.isfinite(value) for value in (used_frac, pacing_ratio, window_hours)):
        return None
    if used_frac < 0.0 or pacing_ratio < 0.0 or window_hours <= 0.0:
        return None
    if used_frac >= 1.0:
        return 0.0
    if pacing_ratio == 0.0:
        return math.inf
    return (1.0 - used_frac) * window_hours / pacing_ratio
