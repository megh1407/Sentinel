"""
SENTINEL - Gas Intelligence Agent
Explosion service for detecting explosive atmosphere conditions.
"""

from typing import Dict, List, Optional, Tuple
from engine.enums import Severity
from sentinel_common.logging import get_logger

logger = get_logger(__name__)


class ExplosionService:
    """
    Service for detecting explosive atmosphere conditions.
    
    Responsible for:
    - Lower Explosive Limit (LEL) monitoring
    - Explosive atmosphere detection
    - Oxygen deficiency analysis
    - Ignition risk assessment
    """
    
    def __init__(self) -> None:
        """Initialize explosion service."""
        self._explosion_stats: Dict[str, int] = {
            "total_checks": 0,
            "explosive_conditions_detected": 0
        }
        logger.info("ExplosionService initialized")
    
    async def check_explosive_atmosphere(
        self,
        methane_ppm: float,
        oxygen_percent: float,
        temperature_celsius: float
    ) -> Tuple[bool, Severity, str]:
        """
        Check for explosive atmosphere conditions.
        
        Args:
            methane_ppm: Methane concentration in ppm
            oxygen_percent: Oxygen concentration in percentage
            temperature_celsius: Temperature in Celsius
            
        Returns:
            Tuple[bool, Severity, str]: (is_explosive, severity, description)
        """
        self._explosion_stats["total_checks"] += 1
        
        # Calculate LEL percentage
        lel_percentage = await self.calculate_lel_percentage(methane_ppm)
        
        # Check conditions for explosion
        is_explosive = False
        severity = Severity.NORMAL
        description = "No explosion hazard detected"
        
        # LEL threshold is typically 5-15% for methane
        # Using 5% as critical threshold
        if lel_percentage >= 5.0:
            is_explosive = True
            severity = Severity.CRITICAL
            description = f"Explosive atmosphere detected: LEL at {lel_percentage:.1f}%"
            self._explosion_stats["explosive_conditions_detected"] += 1
        elif lel_percentage >= 1.0:
            is_explosive = True
            severity = Severity.HIGH
            description = f"High explosion risk: LEL at {lel_percentage:.1f}%"
            self._explosion_stats["explosive_conditions_detected"] += 1
        elif lel_percentage >= 0.5:
            is_explosive = False
            severity = Severity.WARNING
            description = f"Elevated explosion risk: LEL at {lel_percentage:.1f}%"
        
        # Check oxygen deficiency (explosions require oxygen)
        if oxygen_percent < 19.5 and lel_percentage > 0:
            severity = Severity.CRITICAL
            description += " with oxygen deficiency - reduced explosion risk but toxic atmosphere"
        
        # Check temperature (ignition source)
        if temperature_celsius > 537:  # Auto-ignition temperature of methane
            is_explosive = True
            severity = Severity.CRITICAL
            description = "Temperature exceeds auto-ignition point - immediate explosion risk"
        
        return is_explosive, severity, description
    
    async def calculate_lel_percentage(self, methane_ppm: float) -> float:
        """
        Calculate Lower Explosive Limit (LEL) percentage.
        
        Args:
            methane_ppm: Methane concentration in ppm
            
        Returns:
            float: LEL percentage (0-100)
        """
        # Methane LEL is 50,000 ppm (5% by volume)
        lel_threshold = 50000.0
        
        lel_percentage = (methane_ppm / lel_threshold) * 100.0
        return min(100.0, max(0.0, lel_percentage))
    
    async def assess_ignition_risk(
        self,
        gas_concentrations: Dict[str, float],
        temperature: float,
        pressure: float
    ) -> Tuple[bool, Severity, str]:
        """
        Assess ignition risk based on gas concentrations and conditions.
        
        Args:
            gas_concentrations: Dictionary of gas concentrations
            temperature: Temperature in Celsius
            pressure: Pressure in bar
            
        Returns:
            Tuple[bool, Severity, str]: (has_risk, severity, description)
        """
        has_risk = False
        severity = Severity.NORMAL
        risk_factors = []
        
        # Check for flammable gases
        methane = gas_concentrations.get("methane", 0)
        voc = gas_concentrations.get("voc", 0)
        
        if methane > 1000 or voc > 200:
            has_risk = True
            risk_factors.append("flammable gases present")
        
        # Check temperature
        if temperature > 200:
            has_risk = True
            risk_factors.append("elevated temperature")
        
        if temperature > 537:
            severity = Severity.CRITICAL
            risk_factors.append("temperature exceeds auto-ignition point")
        
        # Check pressure
        if pressure > 5.0:
            has_risk = True
            risk_factors.append("high pressure")
        
        # Determine severity
        if has_risk:
            if len(risk_factors) >= 2:
                severity = Severity.HIGH
            else:
                severity = Severity.WARNING
        
        description = f"Ignition risk factors: {', '.join(risk_factors)}" if risk_factors else "No ignition risk detected"
        
        return has_risk, severity, description
    
    def check_oxygen_deficiency(self, oxygen_percent: float) -> Tuple[bool, Optional[Severity]]:
        """
        Check for oxygen deficiency conditions.
        
        Args:
            oxygen_percent: Oxygen concentration in percentage
            
        Returns:
            Tuple[bool, Optional[Severity]]: (is_deficient, severity)
        """
        if oxygen_percent < 16.0:
            return True, Severity.CRITICAL
        elif oxygen_percent < 19.5:
            return True, Severity.WARNING
        elif oxygen_percent > 23.5:
            return True, Severity.WARNING
        else:
            return False, None
    
    async def detect_explosion_hazards(
        self,
        readings: Dict[str, float]
    ) -> List[Dict[str, any]]:
        """
        Detect all explosion-related hazards.
        
        Args:
            readings: Dictionary of gas concentrations and environmental data
            
        Returns:
            List[Dict[str, any]]: List of detected hazards
        """
        hazards = []
        
        methane = readings.get("methane", 0)
        oxygen = readings.get("oxygen", 100)
        temperature = readings.get("temperature", 25)
        
        # Check explosive atmosphere
        is_explosive, severity, description = await self.check_explosive_atmosphere(
            methane, oxygen, temperature
        )
        
        if is_explosive:
            lel_percentage = await self.calculate_lel_percentage(methane)
            hazards.append({
                "type": "EXPLOSIVE_ATMOSPHERE",
                "severity": severity,
                "description": description,
                "lel_percentage": lel_percentage,
                "methane_ppm": methane,
                "oxygen_percent": oxygen
            })
        
        # Check oxygen deficiency
        is_deficient, deficiency_severity = self.check_oxygen_deficiency(oxygen)
        if is_deficient and deficiency_severity:
            hazards.append({
                "type": "OXYGEN_DEFICIENCY",
                "severity": deficiency_severity,
                "description": f"Oxygen level at {oxygen}% - unsafe for combustion",
                "oxygen_percent": oxygen
            })
        
        # Check ignition risk
        has_ignition_risk, ignition_severity, ignition_desc = await self.assess_ignition_risk(
            readings, temperature, readings.get("pressure", 1.0)
        )
        
        if has_ignition_risk:
            hazards.append({
                "type": "IGNITION_RISK",
                "severity": ignition_severity,
                "description": ignition_desc,
                "temperature_celsius": temperature
            })
        
        return hazards
    
    async def assess_explosion_probability(
        self,
        methane_ppm: float,
        oxygen_percent: float,
        trend: str,
        prediction_growth_rate: float,
        leak_probability: str
    ) -> Tuple[str, Severity, str]:
        """
        Assess explosion probability using multi-factor analysis.
        
        Uses: methane, oxygen, trend, prediction, leak probability.
        Does NOT use auto-ignition temperature (future: Permit Agent).
        
        Args:
            methane_ppm: Methane concentration
            oxygen_percent: Oxygen percentage
            trend: Trend direction
            prediction_growth_rate: Predicted growth rate
            leak_probability: Leak probability level
            
        Returns:
            Tuple[str, Severity, str]: (probability, severity, description)
        """
        score = 0.0
        
        # Factor 1: LEL percentage (base score)
        lel = await self.calculate_lel_percentage(methane_ppm)
        score += min(40.0, lel * 8)
        
        # Factor 2: Oxygen availability (explosions need oxygen)
        if 19.5 <= oxygen_percent <= 23.5:
            score += 15
        elif oxygen_percent > 23.5:
            score += 10
        else:
            score -= 10  # Reduced explosion risk in low oxygen
        
        # Factor 3: Trend impact
        if trend == "RAPID_INCREASE":
            score += 15
        elif trend == "INCREASING":
            score += 10
        
        # Factor 4: Prediction growth rate
        if prediction_growth_rate > 0:
            score += min(15.0, prediction_growth_rate * 2)
        
        # Factor 5: Leak probability
        if leak_probability in ["HIGH", "CRITICAL"]:
            score += 15
        
        # Classify
        score = min(100.0, max(0.0, score))
        
        if score >= 70:
            return "CRITICAL", Severity.CRITICAL, f"Critical explosion probability: score {score:.0f}"
        elif score >= 50:
            return "HIGH", Severity.HIGH, f"High explosion probability: score {score:.0f}"
        elif score >= 25:
            return "MEDIUM", Severity.WARNING, f"Medium explosion probability: score {score:.0f}"
        else:
            return "LOW", Severity.NORMAL, f"Low explosion probability: score {score:.0f}"
    
    def get_explosion_stats(self) -> Dict[str, int]:
        """
        Get explosion detection statistics.
        
        Returns:
            Dict[str, int]: Explosion statistics
        """
        return self._explosion_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset explosion statistics."""
        self._explosion_stats = {
            "total_checks": 0,
            "explosive_conditions_detected": 0
        }
        logger.debug("Explosion statistics reset")