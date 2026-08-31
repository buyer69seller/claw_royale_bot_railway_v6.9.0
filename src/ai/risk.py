# src/ai/risk.py
"""Risk Assessment - Menilai risiko setiap action"""

import logging
from typing import Dict, Any, List

from .perception import PerceivedState

logger = logging.getLogger(__name__)

class RiskAssessor:
    def __init__(self):
        self.risk_threshold = 0.7
    
    def assess_action_risk(self, action: Dict, state: PerceivedState) -> Dict[str, Any]:
        if action is None:
            return {"risk_score": 0.5, "is_safe": False, "risk_level": "medium", "factors": []}
        
        action_type = action.get("type")
        if action_type is None:
            return {"risk_score": 0.3, "is_safe": True, "risk_level": "low", "factors": []}
        
        target = action.get("target")
        target_id = None
        if target and isinstance(target, dict):
            target_id = target.get("id")
        
        risk_factors = []
        
        if action_type == "attack":
            risk_factors = self._assess_attack_risk(target_id, state)
        elif action_type == "pickup":
            risk_factors = self._assess_pickup_risk(target_id, state)
        elif action_type in ("interact", "explore"):
            risk_factors = self._assess_interact_risk(target_id, state)
        elif action_type == "move":
            risk_factors = self._assess_move_risk(target_id, state)
        else:
            risk_factors = [{"factor": "unknown_action", "weight": 0.5}]
        
        total_risk = sum(f["weight"] for f in risk_factors)
        max_risk = len(risk_factors) * 1.0
        risk_score = min(total_risk / max_risk if max_risk > 0 else 0, 1.0)
        is_safe = risk_score < self.risk_threshold
        
        return {
            "risk_score": risk_score,
            "is_safe": is_safe,
            "risk_level": "low" if risk_score < 0.3 else "medium" if risk_score < 0.6 else "high",
            "factors": risk_factors
        }
    
    def _assess_attack_risk(self, target_id: str, state: PerceivedState) -> List[Dict]:
        risks = []
        if not target_id:
            risks.append({"factor": "no_target", "weight": 0.5})
            return risks
        
        target = next((e for e in state.enemies if e.id == target_id), None)
        if not target:
            risks.append({"factor": "target_not_found", "weight": 0.8})
            return risks
        
        if state.hp_ratio < 0.3:
            risks.append({"factor": "critical_hp", "weight": 0.9})
        elif state.hp_ratio < 0.5:
            risks.append({"factor": "low_hp", "weight": 0.6})
        
        if target.is_guardian:
            risks.append({"factor": "guardian_target", "weight": 0.9})
        elif target.threat_score > 30:
            risks.append({"factor": "high_threat_target", "weight": 0.7})
        
        target_hp_ratio = target.hp / max(target.max_hp, 1)
        if target_hp_ratio < 0.2:
            risks.append({"factor": "target_almost_dead", "weight": 0.1})
        elif target_hp_ratio > 0.7:
            risks.append({"factor": "target_healthy", "weight": 0.5})
        
        nearby_enemies = len([e for e in state.enemies if e.id != target_id and e.distance < 10])
        if nearby_enemies > 2:
            risks.append({"factor": "outnumbered", "weight": 0.8})
        elif nearby_enemies > 0:
            risks.append({"factor": "other_enemies", "weight": 0.4})
        
        return risks
    
    def _assess_pickup_risk(self, target_id: str, state: PerceivedState) -> List[Dict]:
        risks = []
        if not target_id:
            risks.append({"factor": "no_item", "weight": 0.3})
            return risks
        
        item = next((i for i in state.items if i.id == target_id), None)
        if not item:
            risks.append({"factor": "item_not_found", "weight": 0.5})
            return risks
        
        nearby_enemies = len([e for e in state.enemies if e.distance < 8])
        if nearby_enemies > 0:
            risks.append({"factor": "enemies_nearby", "weight": 0.6})
        
        if state.danger_level > 40:
            risks.append({"factor": "dangerous_area", "weight": 0.7})
        
        if item.value_score > 50:
            risks.append({"factor": "high_value_item", "weight": 0.1})
        
        return risks
    
    def _assess_interact_risk(self, target_id: str, state: PerceivedState) -> List[Dict]:
        risks = []
        if not target_id:
            risks.append({"factor": "no_object", "weight": 0.3})
            return risks
        
        interactable = next((i for i in state.interactables if i.id == target_id), None)
        if not interactable:
            risks.append({"factor": "object_not_found", "weight": 0.5})
            return risks
        
        kind = str(interactable.metadata.get("kind", ""))
        if "ruin" in kind:
            alert = state.region.get("alertGauge", 0)
            if alert > 8:
                risks.append({"factor": "high_alert", "weight": 0.8})
            elif alert > 5:
                risks.append({"factor": "medium_alert", "weight": 0.5})
        
        if interactable.metadata.get("is_exit"):
            risks.append({"factor": "exiting_cave", "weight": 0.1})
        
        nearby_enemies = len([e for e in state.enemies if e.distance < 10])
        if nearby_enemies > 0:
            risks.append({"factor": "enemies_nearby", "weight": 0.5})
        
        return risks
    
    def _assess_move_risk(self, target_id: str, state: PerceivedState) -> List[Dict]:
        risks = []
        if not target_id:
            risks.append({"factor": "no_connection", "weight": 0.3})
            return risks
        
        conn = next((c for c in state.connections if c.id == target_id), None)
        if not conn:
            risks.append({"factor": "connection_not_found", "weight": 0.5})
            return risks
        
        if conn.metadata.get("insideDeathZone", False):
            risks.append({"factor": "death_zone", "weight": 0.9})
        
        safety = float(conn.metadata.get("safetyScore", conn.metadata.get("zoneSafety", 0)))
        if safety < 0.3:
            risks.append({"factor": "unsafe_zone", "weight": 0.7})
        
        return risks
    
    def assess_current_situation(self, state: PerceivedState) -> Dict[str, Any]:
        risk_factors = []
        
        if state.hp_ratio < 0.3:
            risk_factors.append({"factor": "critical_hp", "weight": 0.9})
        elif state.hp_ratio < 0.5:
            risk_factors.append({"factor": "low_hp", "weight": 0.6})
        
        enemy_count = len(state.enemies)
        if enemy_count > 3:
            risk_factors.append({"factor": "many_enemies", "weight": 0.8})
        elif enemy_count > 1:
            risk_factors.append({"factor": "multiple_enemies", "weight": 0.5})
        
        if any(e.is_guardian for e in state.enemies):
            risk_factors.append({"factor": "guardian_present", "weight": 0.8})
        
        if state.in_cave:
            risk_factors.append({"factor": "in_cave", "weight": 0.4})
        
        alert = state.region.get("alertGauge", 0)
        if alert > 8:
            risk_factors.append({"factor": "high_alert", "weight": 0.7})
        
        total_weight = sum(f["weight"] for f in risk_factors)
        max_weight = len(risk_factors) * 1.0
        risk_score = min(total_weight / max_weight if max_weight > 0 else 0, 1.0)
        
        return {
            "risk_score": risk_score,
            "risk_level": "low" if risk_score < 0.3 else "medium" if risk_score < 0.6 else "high",
            "factors": risk_factors,
            "should_flee": risk_score > 0.7,
            "should_heal": state.hp_ratio < 0.4
        }