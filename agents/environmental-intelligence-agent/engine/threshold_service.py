"""
SENTINEL - Gas Intelligence Agent
Threshold service for monitoring gas concentration thresholds.
"""

from typing import Dict, List, Optional, Tuple, Any
from engine.enums import Severity
from config import settings
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class ThresholdService:
    """
    Service for managing and checking gas concentration thresholds.
    
    Responsible for:
    - Threshold configuration management
    - Threshold violation detection
    - Severity level determination
    - Multi-threshold monitoring
    """
    
    def __init__(self) -> None:
        """Initialize threshold service."""
        self._threshold_stats: Dict[str, int] = {
            "total_checks": 0,
            "violations_detected": 0
        }
        logger.info("ThresholdService initialized")
    
    async def check_threshold(
        self,
        gas_type: str,
        value: float
    ) -> Tuple[bool, Optional[Severity], Optional[str]]:
        """
        Check if a gas concentration exceeds any threshold.
        
        Args:
            gas_type: Type of gas (e.g., 'methane', 'carbon_monoxide')
            value: Concentration value
            
        Returns:
            Tuple[bool, Optional[Severity], Optional[str]]: 
                (is_exceeded, severity_level, threshold_name)
        """
        self._threshold_stats["total_checks"] += 1
        
        # Get thresholds from config
        thresholds = self._get_thresholds_for_gas(gas_type)
        if not thresholds:
            return False, None, None
        
        # Check thresholds in order of severity
        severity_order = [
            (Severity.CRITICAL, "critical", lambda v, t: v >= t),
            (Severity.HIGH, "high", lambda v, t: v >= t),
            (Severity.WARNING, "warning", lambda v, t: v >= t),
            (Severity.ADVISORY, "advisory", lambda v, t: v >= t)
        ]
        
        for severity, threshold_name, check_func in severity_order:
            if threshold_name in thresholds:
                threshold_value = thresholds[threshold_name]
                if check_func(value, threshold_value):
                    self._threshold_stats["violations_detected"] += 1
                    return True, severity, threshold_name
        
        return False, None, None
    
    async def check_all_thresholds(self, readings: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Check all gas concentrations against their thresholds.
        
        Args:
            readings: Dictionary of gas types and their concentrations
            
        Returns:
            List[Dict[str, Any]]: List of threshold violations
        """
        violations = []
        
        for gas_type, value in readings.items():
            is_exceeded, severity, threshold_name = await self.check_threshold(gas_type, value)
            if is_exceeded and severity and threshold_name:
                violations.append({
                    "gas_type": gas_type,
                    "value": value,
                    "severity": severity,
                    "threshold_name": threshold_name,
                    "threshold_value": self._get_threshold_value(gas_type, threshold_name)
                })
        
        return violations
    
    def _get_thresholds_for_gas(self, gas_type: str) -> Dict[str, float]:
        """
        Get all thresholds for a specific gas type from config.
        
        Args:
            gas_type: Type of gas
            
        Returns:
            Dict[str, float]: Dictionary of threshold names and values
        """
        # Map gas types to config attributes
        gas_threshold_map = {
            "methane": "THRESHOLD_METHANE_PPM",
            "carbon_monoxide": "THRESHOLD_CARBON_MONOXIDE_PPM",
            "hydrogen_sulfide": "THRESHOLD_HYDROGEN_SULFIDE_PPM",
            "oxygen": "THRESHOLD_OXYGEN_PERCENT",
            "voc": "THRESHOLD_VOC_PPM",
            "ammonia": "THRESHOLD_AMMONIA_PPM",
            "temperature": "THRESHOLD_TEMPERATURE_CELSIUS",
            "humidity": "THRESHOLD_HUMIDITY_PERCENT",
            "pressure": "THRESHOLD_PRESSURE_PSI"
        }
        
        config_key = gas_threshold_map.get(gas_type)
        if not config_key:
            return {}
        
        # Get threshold value from config
        threshold_value = getattr(settings, config_key, None)
        if threshold_value is None:
            return {}
        
        # Return threshold with standard severity levels
        # For simplicity, using the configured value as the WARNING threshold
        # and deriving others proportionally
        return {
            "advisory": threshold_value * 0.5,
            "warning": threshold_value,
            "high": threshold_value * 2.0,
            "critical": threshold_value * 5.0
        }
    
    def _get_threshold_value(self, gas_type: str, threshold_name: str) -> Optional[float]:
        """
        Get a specific threshold value for a gas type.
        
        Args:
            gas_type: Type of gas
            threshold_name: Name of threshold (e.g., 'warning', 'critical')
            
        Returns:
            Optional[float]: Threshold value or None if not found
        """
        thresholds = self._get_thresholds_for_gas(gas_type)
        return thresholds.get(threshold_name)
    
    def get_all_thresholds(self, gas_type: str) -> Dict[str, float]:
        """
        Get all thresholds for a specific gas type.
        
        Args:
            gas_type: Type of gas
            
        Returns:
            Dict[str, float]: Dictionary of threshold names and values
        """
        return self._get_thresholds_for_gas(gas_type)

    def get_threshold(self, gas_type: str, threshold_name: str) -> Optional[float]:
        """Return a single threshold value for a gas type."""
        return self._get_threshold_value(gas_type, threshold_name)
    
    def update_threshold(self, gas_type: str, threshold_name: str, value: float) -> None:
        """
        Update a threshold value.
        
        Note: This updates the runtime threshold. In production, this would
        persist to configuration storage.
        
        Args:
            gas_type: Type of gas
            threshold_name: Name of threshold
            value: New threshold value
        """
        # Placeholder for threshold update logic
        # In production, this would update the config or database
        logger.info(f"Threshold update requested: {gas_type}.{threshold_name} = {value}")
    
    def get_threshold_stats(self) -> Dict[str, int]:
        """
        Get threshold checking statistics.
        
        Returns:
            Dict[str, int]: Threshold statistics
        """
        return self._threshold_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset threshold statistics."""
        self._threshold_stats = {
            "total_checks": 0,
            "violations_detected": 0
        }
        logger.debug("Threshold statistics reset")