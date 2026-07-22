"""
SENTINEL - Gas Intelligence Agent
Correlation service for detecting relationships between gas readings.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from engine.enums import Severity
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class CorrelationService:
    """
    Service for detecting correlations between gas readings and events.
    
    Responsible for:
    - Multi-gas correlation analysis
    - Temporal relationship detection
    - Pattern correlation
    - Compound hazard identification
    """
    
    def __init__(self) -> None:
        """Initialize correlation service."""
        self._correlation_stats: Dict[str, int] = {
            "total_analyses": 0,
            "correlations_found": 0
        }
        logger.info("CorrelationService initialized")
    
    async def find_correlations(
        self,
        gas_readings: Dict[str, float],
        trends: Dict[str, any]
    ) -> List[Dict[str, any]]:
        """
        Find correlations between different gas readings and trends.
        
        Args:
            gas_readings: Dictionary mapping gas types to current values
            trends: Dictionary mapping gas types to trend information
            
        Returns:
            List[Dict[str, any]]: List of detected correlations
        """
        self._correlation_stats["total_analyses"] += 1
        correlations = []
        
        # Define known hazard patterns
        hazard_patterns = [
            {
                "name": "TOXIC_ATMOSPHERE",
                "gases": ["carbon_monoxide", "hydrogen_sulfide"],
                "condition": lambda readings: (
                    readings.get("carbon_monoxide", 0) > 35 and
                    readings.get("hydrogen_sulfide", 0) > 10
                ),
                "severity": Severity.CRITICAL,
                "description": "CO + H2S combination creates toxic atmosphere"
            },
            {
                "name": "EXPLOSION_HAZARD",
                "gases": ["methane"],
                "condition": lambda readings: (
                    readings.get("methane", 0) > 1000 and
                    readings.get("oxygen", 100) > 19.5
                ),
                "severity": Severity.HIGH,
                "description": "Methane with normal oxygen creates explosion risk"
            },
            {
                "name": "ELEVATED_FIRE_RISK",
                "gases": ["methane", "voc"],
                "condition": lambda readings: (
                    readings.get("methane", 0) > 500 and
                    readings.get("voc", 0) > 200
                ),
                "severity": Severity.WARNING,
                "description": "Multiple flammable gases detected"
            },
            {
                "name": "OXYGEN_DEFICIENCY",
                "gases": ["oxygen"],
                "condition": lambda readings: (
                    readings.get("oxygen", 100) < 19.5
                ),
                "severity": Severity.HIGH,
                "description": "Oxygen deficiency detected"
            },
            {
                "name": "COMPOUND_HAZARD",
                "gases": ["methane", "carbon_monoxide", "hydrogen_sulfide"],
                "condition": lambda readings: (
                    readings.get("methane", 0) > 500 and
                    readings.get("carbon_monoxide", 0) > 35 and
                    readings.get("hydrogen_sulfide", 0) > 10
                ),
                "severity": Severity.CRITICAL,
                "description": "Multiple hazardous gases detected simultaneously"
            }
        ]
        
        # Check each pattern
        for pattern in hazard_patterns:
            if pattern["condition"](gas_readings):
                correlation = {
                    "name": pattern["name"],
                    "severity": pattern["severity"],
                    "description": pattern["description"],
                    "gases_involved": pattern["gases"],
                    "gas_values": {gas: gas_readings.get(gas, 0) for gas in pattern["gases"]}
                }
                correlations.append(correlation)
        
        # Check for increasing trends correlation
        increasing_gases = [
            gas for gas, trend_info in trends.items()
            if trend_info.get("trend") in ["INCREASING", "RAPID_INCREASE"]
        ]
        
        if len(increasing_gases) >= 3:
            correlations.append({
                "name": "MULTIPLE_INCREASING_TRENDS",
                "severity": Severity.WARNING,
                "description": f"Multiple gases showing increasing trends: {', '.join(increasing_gases)}",
                "gases_involved": increasing_gases,
                "gas_values": {gas: gas_readings.get(gas, 0) for gas in increasing_gases}
            })
        
        if correlations:
            self._correlation_stats["correlations_found"] += 1
        
        return correlations
    
    async def correlate_events(
        self,
        events: List[Dict[str, any]],
        max_time_lag: int = 300
    ) -> List[List[Dict[str, any]]]:
        """
        Correlate multiple events based on temporal proximity.
        
        Args:
            events: List of event dictionaries
            max_time_lag: Maximum time lag in seconds for correlation
            
        Returns:
            List[List[Dict[str, any]]]: List of correlated event groups
        """
        # Placeholder for event correlation logic
        # Will group events that occur within max_time_lag seconds
        return []
    
    def calculate_correlation_coefficient(
        self,
        values_a: List[float],
        values_b: List[float]
    ) -> float:
        """
        Calculate Pearson correlation coefficient between two series.
        
        Args:
            values_a: First series of values
            values_b: Second series of values
            
        Returns:
            float: Correlation coefficient (-1.0 to 1.0)
        """
        if len(values_a) != len(values_b) or len(values_a) < 2:
            return 0.0
        
        try:
            correlation = np.corrcoef(values_a, values_b)[0, 1]
            return float(correlation) if not np.isnan(correlation) else 0.0
        except Exception:
            return 0.0
    
    def detect_temporal_patterns(
        self,
        gas_type: str,
        values: List[float],
        timestamps: List
    ) -> List[Dict[str, any]]:
        """
        Detect temporal patterns in gas readings.
        
        Args:
            gas_type: Type of gas
            values: List of concentration values
            timestamps: List of timestamps
            
        Returns:
            List[Dict[str, any]]: List of detected patterns
        """
        patterns = []
        
        if len(values) < 3:
            return patterns
        
        # Detect rapid increase pattern
        if len(values) >= 3:
            recent_increase = values[-1] - values[-3]
            if recent_increase > 0:
                avg_previous = np.mean(values[:-1])
                if avg_previous > 0:
                    increase_ratio = recent_increase / avg_previous
                    if increase_ratio > 0.5:
                        patterns.append({
                            "pattern": "RAPID_RISE",
                            "gas_type": gas_type,
                            "severity": Severity.WARNING,
                            "description": f"Rapid rise detected: {recent_increase:.2f} increase"
                        })
        
        return patterns
    
    def get_correlation_stats(self) -> Dict[str, int]:
        """
        Get correlation analysis statistics.
        
        Returns:
            Dict[str, int]: Correlation statistics
        """
        return self._correlation_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset correlation statistics."""
        self._correlation_stats = {
            "total_analyses": 0,
            "correlations_found": 0
        }
        logger.debug("Correlation statistics reset")