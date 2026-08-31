# src/strategy/hybrid_strategy.py
"""Hybrid Strategy v7 - 3 Mode Strategy Selector"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)

class StrategyMode(Enum):
    AI_AUTO_PILOT = "ai_auto_pilot"
    COMPETITIVE_V7 = "competitive_v7"
    HYBRID_V7 = "hybrid_v7"

class HybridStrategyV7:
    def __init__(self):
        self.action_builder = ActionBuilder()
        self.turn = 0
        self.current_mode = StrategyMode.HYBRID_V7
        self.mode_history = []
        self.stats = {
            StrategyMode.AI_AUTO_PILOT: {"used": 0, "success": 0},
            StrategyMode.COMPETITIVE_V7: {"used": 0, "success": 0},
            StrategyMode.HYBRID_V7: {"used": 0, "success": 0}
        }
        self._used_interactables = set()
        self._attack_cooldown = 0
        self._pack_modifiers = {}
    
    def set_pack_modifiers(self, main_pack: Dict, sub_pack: Dict):
        self._pack_modifiers = {}
    
    def decide(self, state: GameState, ai_decision: Optional[Dict] = None) -> Dict:
        self.turn += 1
        mode = self._select_mode(state)
        self.current_mode = mode
        self.mode_history.append(mode)
        
        if mode == StrategyMode.AI_AUTO_PILOT:
            decision = self._ai_mode(state, ai_decision)
        elif mode == StrategyMode.COMPETITIVE_V7:
            decision = self._competitive_mode(state)
        else:
            decision = self._hybrid_mode(state, ai_decision)
        
        self.stats[mode]["used"] += 1
        return decision
    
    def _select_mode(self, state: GameState) -> StrategyMode:
        hp_ratio = state.hp_ratio()
        enemy_count = len(state.get_enemies())
        danger = state.alert_gauge
        
        if hp_ratio < 0.25:
            return StrategyMode.COMPETITIVE_V7
        if hp_ratio < 0.40:
            return StrategyMode.HYBRID_V7
        if enemy_count > 3:
            return StrategyMode.HYBRID_V7
        if enemy_count == 0 and hp_ratio > 0.7:
            return StrategyMode.AI_AUTO_PILOT
        if danger > 7:
            return StrategyMode.COMPETITIVE_V7
        return StrategyMode.HYBRID_V7
    
    def _ai_mode(self, state: GameState, ai_decision: Optional[Dict]) -> Dict:
        if ai_decision:
            return ai_decision
        return self._competitive_mode(state)
    
    def _competitive_mode(self, state: GameState) -> Dict:
        return self._priority_decision(state)
    
    def _hybrid_mode(self, state: GameState, ai_decision: Optional[Dict]) -> Dict:
        priority_dec = self._priority_decision(state)
        if priority_dec.get("priority", 5) <= 2:
            return priority_dec
        return priority_dec
    
    def _priority_decision(self, state: GameState) -> Dict:
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
        
        if not state.is_alive:
            return {"kind": "dead", "score": -1e9, "priority": 5}
        
        if state.in_cave:
            cave_exit = state.get_cave_exit()
            if cave_exit:
                return {"kind": "interact", "obj": cave_exit, "score": SCORE_CAVE_EXIT, "priority": 1}
            return {"kind": "wait", "score": 0, "priority": 5}
        
        candidates = []
        hp_ratio = state.hp_ratio()
        
        # Priority 1: Survival
        if hp_ratio < 0.4:
            for item in state.get_items():
                if not isinstance(item, dict):
                    continue
                item_id = item.get("instanceId") or item.get("id")
                if not state.is_item_valid(item_id):
                    continue
                heal = float(item.get("heal", item.get("healAmount", 0)))
                if heal > 0:
                    score = heal_score(item, hp_ratio)
                    candidates.append({"kind": "pickup", "obj": item, "score": score, "priority": 1})
        
        # Priority 2: Retreat
        if hp_ratio < 0.2:
            for conn in state.get_connections():
                if isinstance(conn, str):
                    conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
                elif not isinstance(conn, dict):
                    continue
                if not conn.get("insideDeathZone", False):
                    candidates.append({"kind": "move", "obj": conn, "score": 500, "priority": 2})
        
        # Priority 3: Combat
        if hp_ratio > 0.4 and self._attack_cooldown == 0:
            for enemy in state.get_enemies():
                if not isinstance(enemy, dict):
                    continue
                enemy_hp = float(enemy.get("hp", 0))
                enemy_max_hp = float(enemy.get("maxHp", 1))
                enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
                is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
                if is_guardian and hp_ratio < 0.6:
                    continue
                if enemy_ratio < 0.5:
                    score = combat_score(enemy, hp_ratio)
                    if score > 0:
                        candidates.append({"kind": "attack", "obj": enemy, "score": score, "priority": 3})
        
        # Priority 4-8: Loot, Interact, Explore, Move, Wait
        for item in state.get_items():
            if not isinstance(item, dict):
                continue
            item_id = item.get("instanceId") or item.get("id")
            if not state.is_item_valid(item_id):
                continue
            score = loot_score(item)
            if score > 0:
                candidates.append({"kind": "pickup", "obj": item, "score": score, "priority": 4})
        
        for obj in state.get_interactables():
            if not isinstance(obj, dict):
                continue
            obj_id = obj.get("id") or obj.get("interactableId")
            if obj_id in self._used_interactables:
                continue
            score = interact_score(obj)
            if score > 0:
                candidates.append({"kind": "interact", "obj": obj, "score": score, "priority": 5})
        
        if hp_ratio > 0.6:
            for obj in state.get_interactables():
                if not isinstance(obj, dict):
                    continue
                obj_id = obj.get("id") or obj.get("interactableId")
                if obj_id in self._used_interactables:
                    continue
                score = explore_score(obj, state.get_region())
                if score > 0:
                    candidates.append({"kind": "explore", "obj": obj, "score": score, "priority": 6})
        
        for conn in state.get_connections():
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            score = move_score(conn, state.in_cave)
            if score > 0:
                candidates.append({"kind": "move", "obj": conn, "score": score, "priority": 7})
        
        if not candidates:
            return {"kind": "wait", "score": 0, "priority": 8}
        
        best = max(candidates, key=lambda x: (x["priority"], x["score"]))
        
        if best["kind"] == "attack":
            self._attack_cooldown = 2
        
        if best["kind"] in ("interact", "explore"):
            obj_id = best["obj"].get("id") or best["obj"].get("interactableId")
            if obj_id:
                self._used_interactables.add(obj_id)
        
        if best["kind"] == "pickup":
            item_id = best["obj"].get("instanceId") or best["obj"].get("id")
            if item_id:
                state.mark_item_attempted(item_id)
        
        return best
    
    def execute(self, decision: Dict) -> Optional[Dict]:
        kind = decision.get("kind")
        obj = decision.get("obj", {})
        
        if kind == "dead" or kind == "wait":
            return None
        
        if kind == "pickup":
            return self.action_builder.pickup(obj)
        elif kind == "attack":
            return self.action_builder.attack(obj)
        elif kind == "interact":
            return self.action_builder.interact(obj)
        elif kind == "explore":
            return self.action_builder.explore(obj)
        elif kind == "move":
            if isinstance(obj, str):
                return self.action_builder.move({"regionId": obj})
            return self.action_builder.move(obj)
        
        return None
    
    def reset(self):
        self._used_interactables.clear()
        self._attack_cooldown = 0
        self.turn = 0
        self.mode_history = []
    
    def get_stats(self) -> Dict:
        total = sum(s["used"] for s in self.stats.values())
        return {
            "mode_stats": {
                mode.value: {
                    "used": data["used"],
                    "percentage": (data["used"] / total * 100) if total > 0 else 0
                }
                for mode, data in self.stats.items()
            },
            "current_mode": self.current_mode.value,
            "mode_history": [m.value for m in self.mode_history[-10:]]
        }