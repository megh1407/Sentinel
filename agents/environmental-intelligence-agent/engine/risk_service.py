"""
SENTINEL - Gas Intelligence Agent
Risk service for calculating and assessing overall risk levels.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from engine.enums import Severity
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class RiskService:
    """
    Service for calculating and managing risk scores.
    
    Responsible for:
    - Composite risk scoring
    - Risk level classification
    - Multi-factor risk assessment
    - Risk trend analysis
    """
    
    def __init__(self) -> None:
        """Initialize risk service."""
        self._risk_stats: Dict[str, int] = {
            "total_assessments": 0,
            "high_risk_detected": 0,
            "critical_risk_detected": 0
        }
        logger.info("RiskService initialized")
    
    async def calculate_risk_score(
        self,
        gas_readings: Optional[Dict[str, float]] = None,
        threshold_violations: Optional[List[Dict[str, any]]] = None,
        trends: Optional[Dict[str, any]] = None,
        predictions: Optional[Dict[str, any]] = None,
        correlations: Optional[List[Dict[str, any]]] = None,
        explosion_hazards: Optional[List[Dict[str, any]]] = None,
        sensor_health: Optional[Dict[str, any]] = None,
        environmental_data: Optional[Dict[str, float]] = None,
        events: Optional[List[Dict[str, any]]] = None,
    ) -> Tuple[float, Severity, Dict[str, float]]:
        """
        Calculate composite risk score based on all factors.
        
        Args:
            gas_readings: Dictionary of gas concentrations
            threshold_violations: List of threshold violations
            trends: Dictionary of trend analysis results
            predictions: Dictionary of prediction results
            correlations: List of correlation findings
            explosion_hazards: List of explosion hazards
            sensor_health: Sensor health assessment
            
        Returns:
            Tuple[float, Severity, float, Dict[str, float]]: 
                (risk_score, severity, confidence, score_breakdown)
        """
        self._risk_stats["total_assessments"] += 1

        gas_readings = gas_readings or {}
        threshold_violations = threshold_violations or []
        trends = trends or {}
        predictions = predictions or {}
        correlations = correlations or []
        explosion_hazards = explosion_hazards or []
        sensor_health = sensor_health or {"status": "HEALTHY"}
        environmental_data = environmental_data or {}

        # Calculate individual risk components
        threshold_score = self._calculate_threshold_score(threshold_violations)
        trend_score = self._calculate_trend_score(trends)
        prediction_score = self._calculate_prediction_score(predictions)
        correlation_score = self._calculate_correlation_score(correlations)
        explosion_score = self._calculate_explosion_score(explosion_hazards)
        sensor_health_score = self._calculate_sensor_health_score(sensor_health)
        environmental_score = 0.0
        if environmental_data:
            temperature = environmental_data.get("temperature", 25.0)
            humidity = environmental_data.get("humidity", 50.0)
            pressure = environmental_data.get("pressure", 14.7)
            environmental_score = min(100.0, max(0.0, (abs(temperature - 25) * 1.5) + (max(0.0, humidity - 60) * 0.5) + (max(0.0, pressure - 14.7) * 2.0)))
        
        # Weighted combination
        weights = {
            "threshold": 0.25,
            "trend": 0.15,
            "prediction": 0.15,
            "correlation": 0.20,
            "explosion": 0.20,
            "sensor_health": 0.05
        }
        
        risk_score = (
            threshold_score * weights["threshold"] +
            trend_score * weights["trend"] +
            prediction_score * weights["prediction"] +
            correlation_score * weights["correlation"] +
            explosion_score * weights["explosion"] +
            sensor_health_score * weights["sensor_health"] +
            environmental_score * 0.05
        )
        
        # Ensure score is within bounds
        risk_score = max(0.0, min(100.0, risk_score))
        
        # Classify severity
        severity = self.classify_risk_level(risk_score)
        
        # Track high/critical risks
        if severity in [Severity.HIGH, Severity.CRITICAL]:
            self._risk_stats["high_risk_detected"] += 1
        if severity == Severity.CRITICAL:
            self._risk_stats["critical_risk_detected"] += 1
        
        # Create score breakdown
        score_breakdown = {
            "threshold_score": threshold_score,
            "trend_score": trend_score,
            "prediction_score": prediction_score,
            "correlation_score": correlation_score,
            "explosion_score": explosion_score,
            "sensor_health_score": sensor_health_score,
            "environmental_score": environmental_score,
        }
        
        return risk_score, severity, score_breakdown
    
    def _calculate_threshold_score(self, violations: List[Dict[str, any]]) -> float:
        """
        Calculate risk score from threshold violations.
        
        Args:
            violations: List of threshold violations
            
        Returns:
            float: Threshold risk score (0-100)
        """
        if not violations:
            return 0.0
        
        severity_scores = {
            Severity.ADVISORY: 20.0,
            Severity.WARNING: 40.0,
            Severity.HIGH: 70.0,
            Severity.CRITICAL: 100.0
        }
        
        # Take the maximum severity score
        max_score = 0.0
        for violation in violations:
            severity = violation.get("severity")
            if severity in severity_scores:
                max_score = max(max_score, severity_scores[severity])
        
        return max_score
    
    def _calculate_trend_score(self, trends: Dict[str, any]) -> float:
        """
        Calculate risk score from trend analysis.
        
        Args:
            trends: Dictionary of trend information
            
        Returns:
            float: Trend risk score (0-100)
        """
        if not trends:
            return 0.0
        
        trend_scores = {
            "STABLE": 0.0,
            "INCREASING": 30.0,
            "RAPID_INCREASE": 60.0,
            "DECREASING": 10.0,
            "RAPID_DECREASE": 20.0
        }
        
        # Take the maximum trend score
        max_score = 0.0
        for gas_type, trend_info in trends.items():
            trend_direction = trend_info.get("trend", "STABLE")
            if trend_direction in trend_scores:
                max_score = max(max_score, trend_scores[trend_direction])
        
        return max_score
    
    def _calculate_prediction_score(self, predictions: Dict[str, any]) -> float:
        """
        Calculate risk score from predictions.
        
        Args:
            predictions: Dictionary of prediction results
            
        Returns:
            float: Prediction risk score (0-100)
        """
        if not predictions:
            return 0.0
        
        max_score = 0.0
        
        for gas_type, prediction in predictions.items():
            threshold_crossing = prediction.get("threshold_crossing_minutes")
            
            if threshold_crossing is not None:
                if threshold_crossing == 0:
                    max_score = max(max_score, 100.0)
                elif threshold_crossing <= 5:
                    max_score = max(max_score, 80.0)
                elif threshold_crossing <= 15:
                    max_score = max(max_score, 60.0)
                elif threshold_crossing <= 30:
                    max_score = max(max_score, 40.0)
                else:
                    max_score = max(max_score, 20.0)
        
        return max_score
    
    def _calculate_correlation_score(self, correlations: List[Dict[str, any]]) -> float:
        """
        Calculate risk score from correlations.
        
        Args:
            correlations: List of correlation findings
            
        Returns:
            float: Correlation risk score (0-100)
        """
        if not correlations:
            return 0.0
        
        severity_scores = {
            Severity.ADVISORY: 30.0,
            Severity.WARNING: 50.0,
            Severity.HIGH: 75.0,
            Severity.CRITICAL: 100.0
        }
        
        # Take the maximum severity score
        max_score = 0.0
        for correlation in correlations:
            severity = correlation.get("severity")
            if severity in severity_scores:
                max_score = max(max_score, severity_scores[severity])
        
        return max_score
    
    def _calculate_explosion_score(self, hazards: List[Dict[str, any]]) -> float:
        """
        Calculate risk score from explosion hazards.
        
        Args:
            hazards: List of explosion hazards
            
        Returns:
            float: Explosion risk score (0-100)
        """
        if not hazards:
            return 0.0
        
        severity_scores = {
            Severity.WARNING: 40.0,
            Severity.HIGH: 70.0,
            Severity.CRITICAL: 100.0
        }
        
        # Take the maximum severity score
        max_score = 0.0
        for hazard in hazards:
            severity = hazard.get("severity")
            if severity in severity_scores:
                max_score = max(max_score, severity_scores[severity])
        
        return max_score
    
    def _calculate_sensor_health_score(self, sensor_health: Dict[str, any]) -> float:
        """
        Calculate risk score from sensor health.
        
        Args:
            sensor_health: Sensor health assessment
            
        Returns:
            float: Sensor health risk score (0-100)
        """
        status = sensor_health.get("status")
        
        health_scores = {
            "HEALTHY": 0.0,
            "WARNING": 30.0,
            "FAULT": 70.0,
            "OFFLINE": 100.0
        }
        
        return health_scores.get(status, 50.0)
    
    def calculate_confidence(
        self,
        trends: Dict[str, any],
        predictions: Dict[str, any],
        num_gases: int
    ) -> float:
        """
        Calculate overall confidence in the risk assessment.
        
        Args:
            trends: Trend analysis results
            predictions: Prediction results
            num_gases: Number of gases analyzed
            
        Returns:
            float: Confidence score (0.0-1.0)
        """
        confidence_factors = []
        
        # Data availability confidence
        if num_gases >= 6:
            confidence_factors.append(1.0)
        elif num_gases >= 3:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.4)
        
        # Trend confidence
        if trends:
            trend_confidences = [t.get("confidence", 0.0) for t in trends.values()]
            if trend_confidences:
                confidence_factors.append(np.mean(trend_confidences))
        
        # Prediction confidence
        if predictions:
            prediction_confidences = [p.get("confidence", 0.0) for p in predictions.values()]
            if prediction_confidences:
                confidence_factors.append(np.mean(prediction_confidences))
        
        # Overall confidence
        if confidence_factors:
            return min(1.0, max(0.0, np.mean(confidence_factors)))
        return 0.5
    
    async def assess_individual_gas_risk(
        self,
        gas_type: str,
        concentration: float
    ) -> Tuple[float, Severity]:
        """
        Assess risk for an individual gas type.
        
        Args:
            gas_type: Type of gas
            concentration: Concentration value
            
        Returns:
            Tuple[float, Severity]: (risk_score, severity)
        """
        # Get threshold
        threshold_service = None  # Would be injected in production
        is_exceeded, severity, _ = await self._check_threshold(gas_type, concentration)
        
        if is_exceeded and severity:
            severity_scores = {
                Severity.ADVISORY: 25.0,
                Severity.WARNING: 50.0,
                Severity.HIGH: 75.0,
                Severity.CRITICAL: 100.0
            }
            risk_score = severity_scores.get(severity, 0.0)
            return risk_score, severity
        
        return 0.0, Severity.NORMAL
    
    async def _check_threshold(self, gas_type: str, value: float):
        """Helper to check threshold (would use ThresholdService in production)."""
        from engine.threshold_service import ThresholdService
        threshold_service = ThresholdService()
        return await threshold_service.check_threshold(gas_type, value)
    
    def classify_risk_level(self, risk_score: float) -> Severity:
        """
        Classify risk level based on score.
        
        Args:
            risk_score: Risk score (0-100)
            
        Returns:
            Severity: Risk severity level
        """
        if risk_score >= 95:
            return Severity.CRITICAL
        elif risk_score >= 85:
            return Severity.HIGH
        elif risk_score >= 70:
            return Severity.WARNING
        elif risk_score >= 40:
            return Severity.ADVISORY
        else:
            return Severity.NORMAL
    
    async def calculate_compound_risk(
        self,
        multiple_readings: List[Dict[str, any]]
    ) -> Tuple[float, Severity, List[str]]:
        """
        Calculate compound risk from multiple readings.
        
        Args:
            multiple_readings: List of reading dictionaries
            
        Returns:
            Tuple[float, Severity, List[str]]: 
                (compound_risk_score, severity, risk_factors)
        """
        if not multiple_readings:
            return 0.0, Severity.NORMAL, []
        
        # Calculate average risk across all readings
        risk_scores = []
        for reading in multiple_readings:
            # Simplified compound risk calculation
            risk_scores.append(50.0)  # Placeholder
        
        compound_risk = np.mean(risk_scores) if risk_scores else 0.0
        severity = self.classify_risk_level(compound_risk)
        risk_factors = ["Multiple zones analyzed"]
        
        return compound_risk, severity, risk_factors
    
    def get_risk_factors(
        self,
        gas_readings: Dict[str, float],
        threshold_violations: List[Dict[str, any]]
    ) -> List[str]:
        """
        Identify risk factors from readings and violations.
        
        Args:
            gas_readings: Dictionary of gas concentrations
            threshold_violations: List of threshold violations
            
        Returns:
            List[str]: List of identified risk factors
        """
        risk_factors = []
        
        # Add threshold violations as risk factors
        for violation in threshold_violations:
            gas_type = violation.get("gas_type")
            severity = violation.get("severity")
            if gas_type and severity:
                risk_factors.append(f"{gas_type} {severity} threshold exceeded")
        
        return risk_factors
    
    def get_risk_stats(self) -> Dict[str, int]:
        """
        Get risk assessment statistics.
        
        Returns:
            Dict[str, int]: Risk statistics
        """
        return self._risk_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset risk statistics."""
        self._risk_stats = {
            "total_assessments": 0,
            "high_risk_detected": 0,
            "critical_risk_detected": 0
        }
        logger.debug("Risk statistics reset")