# src/ai/hybrid_engine.py
"""Hybrid AI Engine - AI Auto-Pilot + Competitive v7 + RL"""

import logging
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .perception import PerceivedState, PerceptionEngine
from .analyzer import GameAnalyzer
from .decision import DecisionEngine, AIDecision
from .risk import RiskAssessor
from .knowledge import KnowledgeBase
from ..game.state import GameState
from ..core.constants import ACTION_INTERVAL_SECONDS
from .rl_agent import QLearningAgent

logger = logging.getLogger(__name__)

@dataclass
class ThreatAssessment:
    kill_probability: float
    damage_received: float
    survival_chance: float
    escape_chance: float
    zone_threat: float
    risk_score: float
    is_safe: bool
    should_fight: bool
    should_flee: bool

@dataclass
class PriorityDecision:
    priority: int
    action_type: str
    target_id: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0

class HybridAIEngine:
    def __init__(self):
        self.ai = DecisionEngine()
        self.perception = PerceptionEngine()
        self.analyzer = GameAnalyzer()
        self.risk = RiskAssessor()
        self.knowledge = KnowledgeBase()
        self.rl_agent = QLearningAgent()
        self.turn = 0
        self.kills = 0
        self.survival_time = 0
        self.rl_enabled = True
        
        self.stats = {
            "decisions_made": 0,
            "ai_decisions": 0,
            "heuristic_decisions": 0,
            "survival_priority": 0,
            "kill_priority": 0,
            "loot_priority": 0,
            "explore_priority": 0
        }
        
        self._decision_cache: Dict[int, AIDecision] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._max_cache_size = 50
        self._last_hp = 0
        self._last_turn = 0
    
    async def decide(self, state: GameState) -> AIDecision:
        self.turn += 1
        hp_ratio = state.hp_ratio()
        
        # Early exit for critical HP
        if hp_ratio < 0.15:
            healing_items = state.get_healing_items()
            for item in healing_items[:3]:
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    distance = state._calculate_distance(state.get_self(), item)
                    if distance < 3:
                        item_id = item.get("instanceId") or item.get("id")
                        if item_id:
                            state.mark_item_attempted(item_id)
                            return AIDecision(
                                action_type="pickup",
                                target_id=item_id,
                                confidence=0.98,
                                reasoning=[f"Critical HP ({hp_ratio:.0%}) - emergency healing"],
                                risk_score=0.05,
                                expected_value=1.0
                            )
        
        # Cache check
        if self.turn > 1 and self.turn == self._last_turn + 1:
            hp_changed = abs(hp_ratio - self._last_hp) < 0.05
            cached = self._decision_cache.get(self.turn - 1)
            if cached and hp_changed:
                self._cache_hits += 1
                return cached
        
        self._cache_misses += 1
        self._last_hp = hp_ratio
        self._last_turn = self.turn
        
        perceived = self.perception.perceive(state)
        threat = await self._assess_threat(perceived, state)
        priority_decision = await self._priority_decision(perceived, state, threat)
        
        ai_decision = await self.ai._make_decision(
            perceived,
            self.ai.analyzer.analyze(perceived),
            self.risk.assess_current_situation(perceived)
        )
        
        final_decision = await self._hybrid_selection(priority_decision, ai_decision, perceived, threat)
        
        self.stats["decisions_made"] += 1
        if final_decision.confidence > 0.6:
            self.stats["ai_decisions"] += 1
        else:
            self.stats["heuristic_decisions"] += 1
        
        if self.turn % 10 == 0:
            try:
                item_stats = state.get_item_stats()
                logger.debug(f"📊 Item Stats: {item_stats}")
            except Exception:
                pass
        
        logger.info(f"🧠 Hybrid AI: {final_decision.action_type} (Priority: {priority_decision.priority}, Conf: {final_decision.confidence:.2f})")
        
        if len(self._decision_cache) > self._max_cache_size:
            oldest_keys = sorted(self._decision_cache.keys())[:10]
            for key in oldest_keys:
                del self._decision_cache[key]
        self._decision_cache[self.turn] = final_decision
        
        return final_decision
    
    async def _assess_threat(self, perceived: PerceivedState, state: GameState) -> Dict[str, Any]:
        threat = {
            "kill_probability": 0.0,
            "damage_received": 0.0,
            "survival_chance": 1.0,
            "escape_chance": 1.0,
            "zone_threat": 0.0,
            "risk_score": 0.0,
            "is_safe": True,
            "should_fight": False,
            "should_flee": False
        }
        
        try:
            me = state.get_self()
            if not isinstance(me, dict):
                return threat
            
            my_hp = float(me.get("hp", 0))
            my_max_hp = float(me.get("maxHp", 1))
            my_atk = float(me.get("attack", me.get("atk", 0)))
            my_def = float(me.get("defense", me.get("def", 0)))
            hp_ratio = my_hp / max(my_max_hp, 1)
            
            enemies = state.get_enemies()
            valid_enemies = [e for e in enemies if isinstance(e, dict)]
            
            if valid_enemies:
                closest = min(valid_enemies, key=lambda e: state._calculate_distance(me, e))
                target_hp = float(closest.get("hp", 0))
                target_max_hp = float(closest.get("maxHp", 1))
                target_atk = float(closest.get("attack", closest.get("atk", 0)))
                target_def = float(closest.get("defense", closest.get("def", 0)))
                
                threat["kill_probability"] = max(0, min(1, (my_atk - target_def) / max(target_hp, 1)))
                turns_to_kill = target_hp / max(my_atk - target_def, 1)
                threat["damage_received"] = (target_atk - my_def) * turns_to_kill
                threat["survival_chance"] = max(0, min(1, 1 - (threat["damage_received"] / max(my_hp, 1))))
                enemy_density = len(valid_enemies)
                threat["escape_chance"] = max(0, min(1, 1 - (enemy_density / 10)))
                threat["should_fight"] = hp_ratio > 0.5 and threat["kill_probability"] > 0.6 and threat["survival_chance"] > 0.7
                threat["should_flee"] = hp_ratio < 0.3 or threat["survival_chance"] < 0.5 or threat["kill_probability"] < 0.3
            
            region = state.get_region()
            if isinstance(region, dict) and region.get("insideDeathZone", False):
                threat["zone_threat"] = 0.8
            
            threat["risk_score"] = min(1.0, (1 - hp_ratio) * 0.4 + (1 - threat["survival_chance"]) * 0.3 + threat["zone_threat"] * 0.2 + (1 - threat["escape_chance"]) * 0.1)
            threat["is_safe"] = threat["risk_score"] < 0.4
            
        except Exception as e:
            logger.debug(f"Threat assessment error: {e}")
        
        return threat
    
    async def _priority_decision(self, perceived: PerceivedState, state: GameState, threat: Dict) -> PriorityDecision:
        try:
            me = state.get_self()
            if not isinstance(me, dict):
                return PriorityDecision(priority=5, action_type="wait", reasoning="No self data", confidence=0.1)
            
            my_hp = float(me.get("hp", 0))
            my_max_hp = float(me.get("maxHp", 1))
            hp_ratio = my_hp / max(my_max_hp, 1)
            alert = state.get_region().get("alertGauge", 0)
            
            # Survival
            if hp_ratio < 0.3:
                healing_items = state.get_healing_items()
                for item in healing_items:
                    if not isinstance(item, dict):
                        continue
                    heal = float(item.get("heal", item.get("healAmount", 0)))
                    if heal > 0:
                        distance = state._calculate_distance(state.get_self(), item)
                        if distance < 3:
                            self.stats["survival_priority"] += 1
                            item_id = item.get("instanceId") or item.get("id")
                            if item_id:
                                state.mark_item_attempted(item_id)
                                return PriorityDecision(
                                    priority=1,
                                    action_type="pickup",
                                    target_id=item_id,
                                    reasoning=f"Critical HP ({hp_ratio:.0%}) - healing",
                                    confidence=0.95
                                )
            
            if hp_ratio < 0.2:
                self.stats["survival_priority"] += 1
                for conn in state.get_connections():
                    if isinstance(conn, dict) and not conn.get("insideDeathZone", False):
                        return PriorityDecision(
                            priority=1,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning=f"Critical HP ({hp_ratio:.0%}) - retreating",
                            confidence=0.9
                        )
            
            if state.in_cave:
                for obj in state.get_interactables():
                    if isinstance(obj, dict) and obj.get("isExit", False) and "cave" in str(obj.get("type", "")):
                        self.stats["survival_priority"] += 1
                        return PriorityDecision(
                            priority=1,
                            action_type="interact",
                            target_id=obj.get("interactableId") or obj.get("id"),
                            reasoning="Exiting cave",
                            confidence=0.95
                        )
            
            if alert > 7:
                self.stats["survival_priority"] += 1
                for conn in state.get_connections():
                    if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                        return PriorityDecision(
                            priority=1,
                            action_type="move",
                            target_id=conn.get("regionId"),
                            reasoning=f"High alert ({alert}) - moving to safety",
                            confidence=0.85
                        )
            
            # Loot
            loot_items = state.get_loot_items()
            for item in loot_items:
                if not isinstance(item, dict):
                    continue
                distance = state._calculate_distance(state.get_self(), item)
                if distance < 3:
                    self.stats["loot_priority"] += 1
                    item_id = item.get("instanceId") or item.get("id")
                    if item_id:
                        state.mark_item_attempted(item_id)
                        return PriorityDecision(
                            priority=2,
                            action_type="pickup",
                            target_id=item_id,
                            reasoning="Collecting loot",
                            confidence=0.8
                        )
            
            # Explore
            if hp_ratio > 0.6 and alert < 6:
                for obj in state.get_interactables():
                    if not isinstance(obj, dict):
                        continue
                    obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
                    if "ruin" in obj_type:
                        distance = state._calculate_distance(state.get_self(), obj)
                        if distance < 3:
                            self.stats["explore_priority"] += 1
                            return PriorityDecision(
                                priority=4,
                                action_type="explore",
                                target_id=obj.get("interactableId") or obj.get("id"),
                                reasoning="Farming ruin",
                                confidence=0.8
                            )
            
            # Move
            for conn in state.get_connections():
                if isinstance(conn, dict) and conn.get("safetyScore", 0) > 0.5:
                    return PriorityDecision(
                        priority=4,
                        action_type="move",
                        target_id=conn.get("regionId"),
                        reasoning="Moving to safer area",
                        confidence=0.5
                    )
            
        except Exception as e:
            logger.debug(f"Priority decision error: {e}")
        
        return PriorityDecision(priority=5, action_type="wait", reasoning="No action available", confidence=0.1)
    
    async def _hybrid_selection(self, priority: PriorityDecision, ai: AIDecision, perceived: PerceivedState, threat: Dict) -> AIDecision:
        if priority.confidence > 0.8:
            return AIDecision(
                action_type=priority.action_type,
                target_id=priority.target_id,
                confidence=priority.confidence,
                reasoning=[priority.reasoning, "Priority-based"],
                risk_score=threat.get("risk_score", 0.5),
                expected_value=1 - threat.get("risk_score", 0.5)
            )
        
        if ai.confidence > 0.7 and priority.priority > 2:
            return ai
        
        if priority.priority <= 2:
            return AIDecision(
                action_type=priority.action_type,
                target_id=priority.target_id,
                confidence=priority.confidence,
                reasoning=[priority.reasoning, "Emergency priority"],
                risk_score=threat.get("risk_score", 0.5),
                expected_value=1 - threat.get("risk_score", 0.5)
            )
        
        return ai
    
    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / max(self._cache_hits + self._cache_misses, 1) * 100
        }