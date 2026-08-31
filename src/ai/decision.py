# src/ai/decision.py
"""Decision Engine - AI Decision Making"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .perception import PerceivedState
from .analyzer import GameAnalyzer
from .risk import RiskAssessor

logger = logging.getLogger(__name__)

@dataclass
class AIDecision:
    action_type: str
    target_id: Optional[str] = None
    confidence: float = 0.0
    reasoning: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    expected_value: float = 0.0

class DecisionEngine:
    def __init__(self):
        self.perception = None
        self.analyzer = GameAnalyzer()
        self.risk = RiskAssessor()
        self.decision_history = []
        self.current_strategy = "balanced"
    
    async def _make_decision(self, perceived: PerceivedState, analysis: Dict, situation_risk: Dict) -> AIDecision:
        recommendations = analysis["recommendations"]
        evaluated_actions = []
        
        for rec in recommendations["all"]:
            action = {"type": rec["action"], "target": {"id": rec.get("target")} if rec.get("target") else None}
            risk = self.risk.assess_action_risk(action, perceived)
            expected_value = self._calculate_expected_value(action, perceived, analysis)
            
            if self.current_strategy == "defensive":
                expected_value *= (1 - risk["risk_score"])
            elif self.current_strategy == "aggressive":
                expected_value *= (1 + (1 - risk["risk_score"]) * 0.3)
            
            evaluated_actions.append({
                "action": action,
                "risk": risk,
                "expected_value": expected_value,
                "priority": rec["priority"],
                "reasoning": rec.get("reasoning", "")
            })
        
        evaluated_actions.sort(key=lambda x: x["expected_value"], reverse=True)
        
        if evaluated_actions and evaluated_actions[0]["expected_value"] > 10:
            best = evaluated_actions[0]
            return AIDecision(
                action_type=best["action"]["type"],
                target_id=best["action"]["target"]["id"] if best["action"]["target"] else None,
                confidence=self._calculate_confidence(best, perceived),
                reasoning=[best.get("reasoning", ""), f"Strategy: {self.current_strategy}"],
                risk_score=best["risk"]["risk_score"],
                expected_value=best["expected_value"]
            )
        
        return AIDecision(action_type="wait", confidence=0.5, reasoning=["No good action found"])
    
    def _calculate_expected_value(self, action: Dict, perceived: PerceivedState, analysis: Dict) -> float:
        action_type = action.get("type")
        target = action.get("target", {})
        
        if action_type == "attack":
            enemy = next((e for e in perceived.enemies if e.id == target.get("id")), None)
            if enemy:
                damage_value = (1 - enemy.hp / max(enemy.max_hp, 1)) * 50
                kill_bonus = 30 if enemy.hp < enemy.max_hp * 0.3 else 0
                risk_penalty = enemy.threat_score * 0.5
                return damage_value + kill_bonus - risk_penalty
            return 0
        
        if action_type == "pickup":
            item = next((i for i in perceived.items if i.id == target.get("id")), None)
            if item:
                return item.value_score - item.distance * 0.5
            return 0
        
        if action_type == "explore":
            interactable = next((i for i in perceived.interactables if i.id == target.get("id")), None)
            if interactable:
                return interactable.value_score - interactable.distance * 0.3
            return 0
        
        return 0
    
    def _calculate_confidence(self, best_action: Dict, perceived: PerceivedState) -> float:
        risk_score = best_action["risk"]["risk_score"]
        expected_value = best_action["expected_value"]
        confidence = (1 - risk_score) * 0.6 + min(expected_value / 100, 0.4)
        if perceived.hp_ratio < 0.3:
            confidence *= 0.8
        return min(max(confidence, 0), 1)
    
    def get_strategy_name(self) -> str:
        names = {"defensive": "🛡️ Defensive", "aggressive": "⚔️ Aggressive", "balanced": "⚖️ Balanced", "explore": "🔍 Exploring"}
        return names.get(self.current_strategy, "❓ Unknown")