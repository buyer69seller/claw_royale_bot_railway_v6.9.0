# src/strategy/engine.py
"""Strategy engine (fallback)"""

import logging
from typing import Dict

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score, 
    interact_score, explore_score, move_score
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self):
        self.turn = 0
        self.action_builder = ActionBuilder()
        self._used_interactables = set()
        self._attack_cooldown = 0
    
    def decide(self, state: GameState) -> Dict:
        self.turn += 1
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
        
        if not state.is_alive:
            return {"kind": "dead", "score": -1e9}
        
        if state.in_cave:
            cave_exit = state.get_cave_exit()
            if cave_exit:
                return {"kind": "interact", "obj": cave_exit, "score": SCORE_CAVE_EXIT}
            return {"kind": "wait", "score": 0}
        
        candidates = []
        hp_ratio = state.hp_ratio()
        
        # Healing
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
                    candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # Combat
        if hp_ratio > 0.4 and self._attack_cooldown == 0:
            for enemy in state.get_enemies():
                if not isinstance(enemy, dict):
                    continue
                enemy_ratio = float(enemy.get("hp", 0)) / max(float(enemy.get("maxHp", 1)), 1)
                is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
                if is_guardian and hp_ratio < 0.6:
                    continue
                if enemy_ratio < 0.5:
                    score = combat_score(enemy, hp_ratio)
                    if score > 0:
                        candidates.append({"kind": "attack", "obj": enemy, "score": score})
        
        # Loot
        for item in state.get_items():
            if not isinstance(item, dict):
                continue
            item_id = item.get("instanceId") or item.get("id")
            if not state.is_item_valid(item_id):
                continue
            score = loot_score(item)
            if score > 0:
                candidates.append({"kind": "pickup", "obj": item, "score": score})
        
        # Interact
        for obj in state.get_interactables():
            if not isinstance(obj, dict):
                continue
            obj_id = obj.get("id") or obj.get("interactableId")
            if obj_id in self._used_interactables:
                continue
            score = interact_score(obj)
            if score > 0:
                candidates.append({"kind": "interact", "obj": obj, "score": score})
        
        # Explore
        if hp_ratio > 0.6:
            for obj in state.get_interactables():
                if not isinstance(obj, dict):
                    continue
                obj_id = obj.get("id") or obj.get("interactableId")
                if obj_id in self._used_interactables:
                    continue
                score = explore_score(obj, state.get_region())
                if score > 0:
                    candidates.append({"kind": "explore", "obj": obj, "score": score})
        
        # Move
        for conn in state.get_connections():
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            score = move_score(conn, state.in_cave)
            if score > 0:
                candidates.append({"kind": "move", "obj": conn, "score": score})
        
        if not candidates:
            return {"kind": "wait", "score": 0}
        
        best = max(candidates, key=lambda x: x["score"])
        
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
    
    def execute(self, state: GameState, decision: Dict):
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