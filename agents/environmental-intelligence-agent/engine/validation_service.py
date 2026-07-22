"""
SENTINEL - Gas Intelligence Agent
Validation service for sensor data validation.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from engine.enums import SensorHealth
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class ValidationService:
    """
    Service for validating sensor readings and data quality.
    
    Responsible for:
    - Input data validation
    - Sensor health assessment
    - Data quality checks
    - Range validation for all parameters
    - Stuck sensor detection
    """
    
    def __init__(self) -> None:
        """Initialize validation service."""
        self._validation_stats: Dict[str, int] = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0
        }
        self._previous_readings: Dict[str, Dict[str, Any]] = {}
        logger.info("ValidationService initialized")
    
    async def validate_reading(self, reading: Dict[str, Any]) -> Tuple[bool, List[str], List[str], Dict[str, Any]]:
        """
        Validate a complete sensor reading.
        
        Returns:
            Tuple[bool, List[str], List[str], Dict[str, Any]]: 
                (is_valid, errors, warnings, sensor_health)
        """
        self._validation_stats["total_validations"] += 1
        errors: List[str] = []
        warnings: List[str] = []
        sensor_health_info: Dict[str, Any] = {
            "status": SensorHealth.HEALTHY,
            "message": "All sensors operational",
            "checks": {}
        }
        
        # Check for missing values (FATAL)
        missing_check = self._check_missing_values(reading)
        errors.extend(missing_check)
        sensor_health_info["checks"]["missing_values"] = len(missing_check) == 0
        
        # Check for negative values (FATAL)
        negative_check = self._check_negative_values(reading)
        errors.extend(negative_check)
        sensor_health_info["checks"]["negative_values"] = len(negative_check) == 0
        
        # Check for impossible readings (FATAL)
        impossible_check = self._check_impossible_readings(reading)
        errors.extend(impossible_check)
        sensor_health_info["checks"]["impossible_readings"] = len(impossible_check) == 0
        
        # Check for out of range values (WARNING - not fatal)
        range_check = self._check_range_violations(reading)
        warnings.extend(range_check)
        sensor_health_info["checks"]["range_violations"] = len(range_check) == 0
        
        # Check sensor status
        status_check, status_msg = self._check_sensor_status(reading)
        warnings.extend(status_check)
        sensor_health_info["checks"]["sensor_status"] = len(status_check) == 0
        if status_msg:
            sensor_health_info["message"] = status_msg
        
        # Check for stuck sensor (WARNING - not fatal)
        sensor_id = reading.get("sensor_id", "")
        if sensor_id:
            stuck_check = self._check_stuck_sensor(sensor_id, reading)
            warnings.extend(stuck_check)
            sensor_health_info["checks"]["stuck_sensor"] = len(stuck_check) == 0
        
        # Determine overall sensor health
        all_checks_passed = all(sensor_health_info["checks"].values())
        if not all_checks_passed:
            failed_checks = [k for k, v in sensor_health_info["checks"].items() if not v]
            if len(failed_checks) >= 3:
                sensor_health_info["status"] = SensorHealth.FAULT
                sensor_health_info["message"] = f"Multiple sensor issues detected: {', '.join(failed_checks)}"
            elif len(failed_checks) >= 1:
                sensor_health_info["status"] = SensorHealth.WARNING
                sensor_health_info["message"] = f"Sensor warnings: {', '.join(failed_checks)}"
        
        # is_valid is ONLY for fatal errors, not warnings
        is_valid = len(errors) == 0
        
        if is_valid:
            self._validation_stats["successful_validations"] += 1
        else:
            self._validation_stats["failed_validations"] += 1
        
        # Store reading for stuck sensor detection
        if sensor_id:
            self._previous_readings[sensor_id] = reading.copy()
        
        return is_valid, errors, warnings, sensor_health_info
    
    def _check_missing_values(self, reading: Dict[str, Any]) -> List[str]:
        """
        Check for missing required values.
        
        Args:
            reading: Sensor reading dictionary
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        required_fields = [
            "timestamp", "sensor_id", "plant", "zone", "line", "equipment",
            "methane", "carbon_monoxide", "hydrogen_sulfide", "oxygen",
            "voc", "ammonia", "temperature", "humidity", "pressure", "sensor_status"
        ]
        
        for field in required_fields:
            if field not in reading or reading[field] is None:
                errors.append(f"Missing required field: {field}")
        
        return errors
    
    def _check_negative_values(self, reading: Dict[str, Any]) -> List[str]:
        """
        Check for negative values in gas concentrations and environmental data.
        
        Args:
            reading: Sensor reading dictionary
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        numeric_fields = [
            "methane", "carbon_monoxide", "hydrogen_sulfide", "oxygen",
            "voc", "ammonia", "temperature", "humidity", "pressure"
        ]
        
        for field in numeric_fields:
            if field in reading and reading[field] is not None:
                if reading[field] < 0:
                    errors.append(f"Negative value detected for {field}: {reading[field]}")
        
        return errors
    
    def _check_impossible_readings(self, reading: Dict[str, Any]) -> List[str]:
        """
        Check for physically impossible readings.
        
        Args:
            reading: Sensor reading dictionary
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Oxygen cannot be 0% in normal atmosphere (sensor failure)
        if "oxygen" in reading and reading["oxygen"] is not None:
            if reading["oxygen"] == 0:
                errors.append("Impossible reading: Oxygen cannot be 0% (sensor failure)")
        
        # All gases cannot be zero simultaneously (sensor failure)
        gas_fields = ["methane", "carbon_monoxide", "hydrogen_sulfide", "voc", "ammonia"]
        all_zero = all(reading.get(field, 0) == 0 for field in gas_fields)
        if all_zero and reading.get("oxygen", 100) == 0:
            errors.append("Impossible reading: All gas sensors reading zero with zero oxygen")
        
        return errors
    
    def _check_range_violations(self, reading: Dict[str, Any]) -> List[str]:
        """
        Check for values outside acceptable ranges.
        
        Args:
            reading: Sensor reading dictionary
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Gas concentration ranges (ppm)
        gas_ranges = {
            "methane": (0, 100000),
            "carbon_monoxide": (0, 10000),
            "hydrogen_sulfide": (0, 1000),
            "oxygen": (0, 100),
            "voc": (0, 10000),
            "ammonia": (0, 1000)
        }
        
        for gas, (min_val, max_val) in gas_ranges.items():
            if gas in reading and reading[gas] is not None:
                value = reading[gas]
                if value < min_val or value > max_val:
                    errors.append(f"{gas} value {value} out of range [{min_val}, {max_val}]")
        
        # Environmental ranges
        if "temperature" in reading and reading["temperature"] is not None:
            temp = reading["temperature"]
            if temp < -50 or temp > 200:
                errors.append(f"Temperature {temp}°C out of range [-50, 200]")
        
        if "humidity" in reading and reading["humidity"] is not None:
            humidity = reading["humidity"]
            if humidity < 0 or humidity > 100:
                errors.append(f"Humidity {humidity}% out of range [0, 100]")
        
        if "pressure" in reading and reading["pressure"] is not None:
            pressure = reading["pressure"]
            if pressure < 0 or pressure > 10:
                errors.append(f"Pressure {pressure} bar out of range [0, 10]")
        
        return errors
    
    def _check_sensor_status(self, reading: Dict[str, Any]) -> Tuple[List[str], Optional[str]]:
        """
        Check sensor health status.
        
        Args:
            reading: Sensor reading dictionary
            
        Returns:
            Tuple[List[str], Optional[str]]: (errors, status_message)
        """
        errors = []
        status_message = None
        
        if "sensor_status" in reading:
            try:
                status = SensorHealth(reading["sensor_status"])
                if status == SensorHealth.OFFLINE:
                    errors.append("Sensor is OFFLINE - readings may be invalid")
                    status_message = "Sensor OFFLINE - data may be unreliable"
                elif status == SensorHealth.FAULT:
                    errors.append("Sensor FAULT detected - readings may be inaccurate")
                    status_message = "Sensor FAULT - data quality compromised"
                elif status == SensorHealth.WARNING:
                    status_message = "Sensor WARNING - monitor closely"
            except ValueError:
                errors.append(f"Invalid sensor_status: {reading['sensor_status']}")
        
        return errors, status_message
    
    def _check_stuck_sensor(self, sensor_id: str, reading: Dict[str, Any]) -> List[str]:
        """
        Check if sensor values are stuck (not changing).
        
        Requires minimum 5 consecutive identical readings before flagging.
        Uses configurable STUCK_SENSOR_WINDOW (default 5).
        
        Args:
            sensor_id: Sensor identifier
            reading: Current sensor reading
            
        Returns:
            List[str]: List of validation warnings
        """
        warnings = []
        stuck_window = getattr(self, '_stuck_window', 5)
        
        if sensor_id not in self._previous_readings:
            return warnings
        
        # Build history chain for this sensor
        if not hasattr(self, '_sensor_history'):
            self._sensor_history: Dict[str, List[Dict[str, Any]]] = {}
        
        if sensor_id not in self._sensor_history:
            self._sensor_history[sensor_id] = []
        
        self._sensor_history[sensor_id].append(reading.copy())
        
        # Keep only last 10 readings
        if len(self._sensor_history[sensor_id]) > 10:
            self._sensor_history[sensor_id] = self._sensor_history[sensor_id][-10:]
        
        history = self._sensor_history[sensor_id]
        
        # Need minimum STUCK_SENSOR_WINDOW readings to detect stucks
        if len(history) < stuck_window:
            return warnings
        
        # Take last N readings
        recent = history[-stuck_window:]
        gas_fields = ["methane", "carbon_monoxide", "hydrogen_sulfide", "oxygen", "voc", "ammonia"]
        
        stuck_gases = []
        for gas in gas_fields:
            values = [r.get(gas) for r in recent if r.get(gas) is not None]
            # All values identical and non-zero = stuck
            if len(values) >= stuck_window and len(set(values)) == 1 and values[0] > 0:
                stuck_gases.append(gas)
        
        if len(stuck_gases) >= len(gas_fields) * 0.5:
            warnings.append(f"Possible stuck sensor detected: {', '.join(stuck_gases)} values unchanged for {stuck_window} readings")
        
        return warnings
    
    def validate_zone(self, zone: str) -> bool:
        """
        Validate zone name format.
        
        Args:
            zone: Zone name to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not zone or len(zone) < 1 or len(zone) > 100:
            return False
        
        import re
        pattern = r'^[a-zA-Z0-9\-_\s]+$'
        return bool(re.match(pattern, zone))
    
    def get_validation_stats(self) -> Dict[str, int]:
        """
        Get validation statistics.
        
        Returns:
            Dict[str, int]: Validation statistics
        """
        return self._validation_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self._validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0
        }
        self._previous_readings.clear()
        logger.debug("Validation statistics reset")