"""
SENTINEL - Gas Intelligence Agent
Historical analytics service for generating statistical insights.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
from engine.history_manager import HistoryManager
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class HistoricalAnalyticsService:
    """
    Service for generating historical analytics from sensor readings.
    
    For each gas, calculates:
    - Current, average, max, min values
    - Peak timestamp, exposure duration
    - Rate of change, trend duration
    - Moving average
    """
    
    def __init__(self, history_manager: HistoryManager) -> None:
        """Initialize with history manager."""
        self.history_manager = history_manager
        logger.info("HistoricalAnalyticsService initialized")
    
    async def generate_analytics(
        self,
        zone: str,
        window_size: int = 50
    ) -> Dict[str, Any]:
        """
        Generate comprehensive historical analytics for a zone.
        
        Args:
            zone: Zone identifier
            window_size: Number of recent readings to analyze
            
        Returns:
            Dict[str, Any]: Per-gas analytics
        """
        history = self.history_manager.get_history(zone, limit=window_size)
        
        if not history:
            return {}
        
        gas_fields = ["methane", "carbon_monoxide", "hydrogen_sulfide",
                      "oxygen", "voc", "ammonia", "temperature", "humidity", "pressure"]
        
        analytics = {}
        for gas in gas_fields:
            values = [r.get(gas, 0) for r in history if r.get(gas) is not None]
            timestamps = [r.get("timestamp") for r in history if r.get(gas) is not None]
            
            if not values or len(values) < 2:
                analytics[gas] = {
                    "current": None,
                    "average": None,
                    "maximum": None,
                    "minimum": None,
                    "peak_timestamp": None,
                    "exposure_duration_minutes": 0,
                    "rate_of_change": 0.0,
                    "trend_duration_minutes": 0,
                    "moving_average": None,
                    "history_length": len(values)
                }
                continue
            
            values_arr = np.array(values)
            current = float(values[-1])
            avg = float(np.mean(values_arr))
            max_val = float(np.max(values_arr))
            min_val = float(np.min(values_arr))
            
            # Peak timestamp
            max_idx = int(np.argmax(values_arr))
            peak_ts = timestamps[max_idx] if max_idx < len(timestamps) else None
            
            # Rate of change (over whole window)
            x = np.arange(len(values_arr))
            slope = float(np.polyfit(x, values_arr, 1)[0])
            
            # Moving average (last 5)
            ma_window = min(5, len(values))
            moving_avg = float(np.mean(values_arr[-ma_window:]))
            
            # Exposure duration based on threshold proximity
            exposure_count = sum(1 for v in values if v > avg * 0.8)
            exposure_duration = exposure_count  # in reading intervals
            
            analytics[gas] = {
                "current": current,
                "average": round(avg, 2),
                "maximum": round(max_val, 2),
                "minimum": round(min_val, 2),
                "peak_timestamp": peak_ts,
                "exposure_duration_minutes": exposure_duration,
                "rate_of_change": round(slope, 4),
                "trend_duration_minutes": len(values),
                "moving_average": round(moving_avg, 2),
                "history_length": len(values)
            }
        
        return analytics