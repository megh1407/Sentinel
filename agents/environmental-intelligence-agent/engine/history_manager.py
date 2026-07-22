"""
SENTINEL - Gas Intelligence Agent
History management for sensor readings and analysis data.
"""

from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from threading import Lock
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SensorReading:
    """
    Data class representing a single sensor reading.
    
    Attributes:
        timestamp: ISO 8601 timestamp of the reading
        zone: Zone identifier
        data: Dictionary containing all sensor measurements
    """
    timestamp: datetime
    zone: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert reading to dictionary format.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the reading
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "zone": self.zone,
            **self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorReading":
        """
        Create SensorReading from dictionary.
        
        Args:
            data: Dictionary containing reading data
            
        Returns:
            SensorReading: Instance created from dictionary
        """
        timestamp = datetime.fromisoformat(data["timestamp"])
        zone = data["zone"]
        reading_data = {k: v for k, v in data.items() if k not in ["timestamp", "zone"]}
        return cls(timestamp=timestamp, zone=zone, data=reading_data)


class ZoneHistory:
    """
    History container for a specific zone.
    
    Maintains a circular buffer of sensor readings with configurable size.
    """
    
    def __init__(self, zone: str, max_size: int = 1000) -> None:
        """
        Initialize zone history.
        
        Args:
            zone: Zone identifier
            max_size: Maximum number of readings to store
        """
        self.zone = zone
        self.max_size = max_size
        self._readings: deque[SensorReading] = deque(maxlen=max_size)
        self._lock = Lock()
        self._oldest_timestamp: Optional[datetime] = None
        self._newest_timestamp: Optional[datetime] = None
    
    def add_reading(self, reading: SensorReading) -> None:
        """
        Add a new reading to the history.
        
        Args:
            reading: SensorReading to add
        """
        with self._lock:
            self._readings.append(reading)
            self._newest_timestamp = reading.timestamp
            
            if self._oldest_timestamp is None or reading.timestamp < self._oldest_timestamp:
                self._oldest_timestamp = reading.timestamp
            
            # Update oldest timestamp if buffer overflowed
            if len(self._readings) == self.max_size:
                self._oldest_timestamp = self._readings[0].timestamp
            
            logger.debug(
                f"Added reading to zone {self.zone}",
                extra={
                    "zone": self.zone,
                    "total_readings": len(self._readings),
                    "timestamp": reading.timestamp.isoformat()
                }
            )
    
    def get_readings(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> List[SensorReading]:
        """
        Retrieve readings from history.
        
        Args:
            limit: Maximum number of readings to return
            since: Only return readings after this timestamp
            
        Returns:
            List[SensorReading]: List of sensor readings
        """
        with self._lock:
            readings = list(self._readings)
            
            # Filter by timestamp if specified
            if since is not None:
                readings = [r for r in readings if r.timestamp >= since]
            
            # Apply limit
            if limit is not None:
                readings = readings[-limit:]
            
            return readings
    
    def get_latest(self, count: int = 1) -> List[SensorReading]:
        """
        Get the most recent readings.
        
        Args:
            count: Number of recent readings to return
            
        Returns:
            List[SensorReading]: List of most recent readings
        """
        with self._lock:
            if count > len(self._readings):
                count = len(self._readings)
            return list(self._readings)[-count:]
    
    def clear(self) -> None:
        """Clear all readings from history."""
        with self._lock:
            self._readings.clear()
            self._oldest_timestamp = None
            self._newest_timestamp = None
            logger.debug(f"Cleared history for zone {self.zone}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the history.
        
        Returns:
            Dict[str, Any]: Statistics including count, oldest, newest timestamps
        """
        with self._lock:
            return {
                "zone": self.zone,
                "count": len(self._readings),
                "max_size": self.max_size,
                "oldest_timestamp": self._oldest_timestamp.isoformat() if self._oldest_timestamp else None,
                "newest_timestamp": self._newest_timestamp.isoformat() if self._newest_timestamp else None
            }
    
    def __len__(self) -> int:
        """Return number of readings in history."""
        return len(self._readings)


class HistoryManager:
    """
    Centralized history manager for all zones.
    
    Provides a unified interface for managing sensor reading history
    across multiple zones with thread-safe operations.
    """
    
    def __init__(self, max_history_size: int = 1000, retention_days: int = 30) -> None:
        """
        Initialize history manager.
        
        Args:
            max_history_size: Maximum number of readings per zone
            retention_days: Number of days to retain readings
        """
        self.max_history_size = max_history_size
        self.retention_days = retention_days
        self._zones: Dict[str, ZoneHistory] = {}
        self._lock = Lock()
        self._cleanup_interval = timedelta(days=1)
        self._last_cleanup = datetime.utcnow()
        
        logger.info(
            "HistoryManager initialized",
            extra={
                "max_history_size": max_history_size,
                "retention_days": retention_days
            }
        )
    
    def _get_or_create_zone(self, zone: str) -> ZoneHistory:
        """
        Get or create zone history.
        
        Args:
            zone: Zone identifier
            
        Returns:
            ZoneHistory: Zone history instance
        """
        if zone not in self._zones:
            self._zones[zone] = ZoneHistory(zone, self.max_history_size)
            logger.debug(f"Created new zone history: {zone}")
        return self._zones[zone]
    
    def add_reading(self, zone: str, reading: SensorReading) -> None:
        """
        Add a sensor reading to zone history.
        
        Args:
            zone: Zone identifier
            reading: SensorReading to add
        """
        zone_history = self._get_or_create_zone(zone)
        zone_history.add_reading(reading)
        
        # Periodic cleanup
        self._maybe_cleanup()
    
    def add_reading_dict(self, zone: str, data: Dict[str, Any]) -> None:
        """
        Add a sensor reading from dictionary.
        
        Args:
            zone: Zone identifier
            data: Dictionary containing reading data
        """
        reading = SensorReading.from_dict(data)
        self.add_reading(zone, reading)
    
    def get_history(
        self,
        zone: str,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical readings for a zone.
        
        Args:
            zone: Zone identifier
            limit: Maximum number of readings to return
            since: Only return readings after this timestamp
            
        Returns:
            List[Dict[str, Any]]: List of readings as dictionaries
        """
        if zone not in self._zones:
            logger.warning(f"No history found for zone: {zone}")
            return []
        
        zone_history = self._zones[zone]
        readings = zone_history.get_readings(limit=limit, since=since)
        
        return [reading.to_dict() for reading in readings]
    
    def get_latest(self, zone: str, count: int = 1) -> List[Dict[str, Any]]:
        """
        Get the most recent readings for a zone.
        
        Args:
            zone: Zone identifier
            count: Number of recent readings to return
            
        Returns:
            List[Dict[str, Any]]: List of most recent readings
        """
        if zone not in self._zones:
            logger.warning(f"No history found for zone: {zone}")
            return []
        
        zone_history = self._zones[zone]
        readings = zone_history.get_latest(count)
        
        return [reading.to_dict() for reading in readings]
    
    def clear_zone(self, zone: str) -> None:
        """
        Clear all history for a specific zone.
        
        Args:
            zone: Zone identifier
        """
        if zone in self._zones:
            self._zones[zone].clear()
            logger.info(f"Cleared history for zone: {zone}")
        else:
            logger.warning(f"No history to clear for zone: {zone}")
    
    def get_zone_stats(self, zone: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific zone.
        
        Args:
            zone: Zone identifier
            
        Returns:
            Optional[Dict[str, Any]]: Zone statistics or None if zone doesn't exist
        """
        if zone not in self._zones:
            return None
        return self._zones[zone].get_stats()
    
    def get_all_zones(self) -> List[str]:
        """
        Get list of all zones with history.
        
        Returns:
            List[str]: List of zone identifiers
        """
        return list(self._zones.keys())
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all zones.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping zone names to their stats
        """
        return {zone: zone_history.get_stats() for zone, zone_history in self._zones.items()}
    
    def _maybe_cleanup(self) -> None:
        """
        Perform cleanup if enough time has passed since last cleanup.
        
        Removes readings older than retention period.
        """
        now = datetime.utcnow()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._cleanup_old_readings()
        self._last_cleanup = now
    
    def _cleanup_old_readings(self) -> None:
        """
        Remove readings older than retention period.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        removed_count = 0
        
        for zone, zone_history in self._zones.items():
            with zone_history._lock:
                old_count = len(zone_history._readings)
                # Filter out old readings
                zone_history._readings = deque(
                    [r for r in zone_history._readings if r.timestamp >= cutoff_date],
                    maxlen=zone_history.max_size
                )
                new_count = len(zone_history._readings)
                removed = old_count - new_count
                removed_count += removed
                
                if removed > 0:
                    logger.debug(
                        f"Cleaned up {removed} old readings from zone {zone}",
                        extra={"zone": zone, "removed": removed}
                    )
        
        if removed_count > 0:
            logger.info(
                f"History cleanup completed",
                extra={"total_removed": removed_count}
            )
    
    def shutdown(self) -> None:
        """Shutdown history manager and cleanup resources."""
        logger.info("Shutting down HistoryManager")
        with self._lock:
            self._zones.clear()
        logger.info("HistoryManager shut down successfully")