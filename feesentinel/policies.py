"""Policy logic for fee spike detection and adjustments."""

from typing import Dict, Any, Optional

def should_alert_spike(current: float, trail_avg: float, config: Dict[str, Any]) -> bool:
    """
    Determine if a fee spike alert should be triggered.
    
    Args:
        current: Current fee estimate (sat/vB)
        trail_avg: Trailing average fee (sat/vB)
        config: Spike detection configuration dictionary
        
    Returns:
        True if alert should be triggered
    """
    if not config.get("enabled", True):
        return False
        
    min_alert = config.get("min_alert_satvb", 15)
    spike_pct = config.get("spike_pct", 35)
    
    if current < min_alert:
        return False
        
    if trail_avg <= 0:
        return False
        
    pct_change = 100.0 * (current - trail_avg) / trail_avg
    return pct_change >= spike_pct


def propose_adjustment(current: float, trail_avg: float, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a policy adjustment proposal based on fee trends.
    
    Args:
        current: Current fee estimate (sat/vB)
        trail_avg: Trailing average fee (sat/vB)
        config: Spike detection configuration dictionary containing adjustment_rules
        
    Returns:
        Dictionary containing the proposal details
    """
    rules = config.get("adjustment_rules", {})
    target_floor = rules.get("target_sat_vb_floor", 12)
    bump_pct = rules.get("bump_pct_if_queue_backlog", 20)
    drop_pct = rules.get("drop_pct_if_clearing_fast", 15)
    
    backlog = current > trail_avg
    
    if backlog:
        # bump suggested floor by a percentage but never below configured floor
        new_floor = max(
            target_floor,
            int(round(current * (1 + bump_pct / 100.0)))
        )
    else:
        new_floor = max(
            target_floor,
            int(round(trail_avg * (1 - drop_pct / 100.0)))
        )
        
    return {
        "type": "policy_adjustment_suggestion",
        "suggested_target_sat_vb": new_floor,
        "basis": {
            "current_sat_vb": round(current, 2),
            "trailing_avg_sat_vb": round(trail_avg, 2),
            "backlog": backlog
        }
    }

