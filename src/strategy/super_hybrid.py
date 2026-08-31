# src/strategy/super_hybrid.py
"""Super Hybrid Strategy - 4 Mode Strategy Engine (Beatdown, Control, Bridge Spam, Siege)"""

import logging
import random
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass, field

from ..game.state import GameState
from ..game.actions import ActionBuilder
from .evaluators import (
    heal_score, combat_score, loot_score,
    interact_score, explore_score, move_score,
    alive, num
)
from ..core.constants import SCORE_CAVE_EXIT

logger = logging.getLogger(__name__)


class SuperMode(Enum):
    """Four distinct playstyles."""
    BEATDOWN = "beatdown"
    CONTROL = "control"
    BRIDGE_SPAM = "bridge_spam"
    SIEGE = "siege"


@dataclass
class ModeStats:
    """Statistics per mode."""
    used: int = 0
    success: int = 0
    kills: int = 0
    items_collected: int = 0
    survival_time: int = 0


class SuperHybridStrategy:
    """
    Super Hybrid Strategy – automatically selects the best mode based on
    game state and executes appropriate actions.
    """

    def __init__(self):
        self.action_builder = ActionBuilder()
        self.turn = 0
        self.current_mode = SuperMode.CONTROL
        self.mode_history = []
        self.mode_stats = {
            SuperMode.BEATDOWN: ModeStats(),
            SuperMode.CONTROL: ModeStats(),
            SuperMode.BRIDGE_SPAM: ModeStats(),
            SuperMode.SIEGE: ModeStats()
        }
        self._used_interactables = set()
        self._attack_cooldown = 0
        self._pack_modifiers = {}
        self._regions_cleared = set()
        self._current_region_id = None
        self._turns_in_region = 0
        self.stats = {
            "total_actions": 0,
            "successful_actions": 0,
            "kills": 0,
            "items_collected": 0,
            "regions_cleared": 0,
            "survival_turns": 0
        }
        # Untuk mencegah loop jika exit cave tidak ditemukan
        self._cave_attempts = 0

    def set_pack_modifiers(self, main_pack: Dict, sub_pack: Dict):
        """Load pack effects to influence decision making."""
        self._pack_modifiers = {}
        if main_pack:
            self._pack_modifiers.update({"defensive": True})
        if sub_pack:
            self._pack_modifiers["heal_priority"] = 2.0

    def decide(self, state: GameState) -> Dict:
        """Main decision entry point."""
        self.turn += 1
        self.stats["survival_turns"] += 1

        # ============================================================
        # HANDLING CAVE – exit as soon as possible, never use move
        # ============================================================
        if state.in_cave:
            self._cave_attempts += 1
            logger.debug(f"🕳️ In cave (attempt {self._cave_attempts})")

            # 1. Try to find the official exit
            exit_obj = state.get_cave_exit()
            if exit_obj:
                logger.info("🚪 SuperHybrid: Exiting cave via detected exit")
                self._cave_attempts = 0
                return {"kind": "interact", "obj": exit_obj, "mode": "siege"}

            # 2. Fallback: interact with any cave-like interactable
            for obj in state.get_interactables():
                if not isinstance(obj, dict):
                    continue
                obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
                if "cave" in obj_type or obj.get("isExit", False):
                    logger.info("🚪 SuperHybrid: Exiting cave via fallback interactable")
                    self._cave_attempts = 0
                    return {"kind": "interact", "obj": obj, "mode": "siege"}

            # 3. After several attempts, try first interactable (desperate)
            if self._cave_attempts > 3:
                interactables = state.get_interactables()
                if interactables:
                    logger.warning("⚠️ SuperHybrid: No exit found, trying first interactable")
                    self._cave_attempts = 0
                    return {"kind": "interact", "obj": interactables[0], "mode": "siege"}

            # 4. Wait – never move while inside cave
            logger.warning("⛔ SuperHybrid: In cave but no exit found – waiting")
            return {"kind": "wait", "mode": "siege"}

        # Reset cave attempt counter when outside
        self._cave_attempts = 0
        # ============================================================

        # Track region changes
        region = state.get_region()
        region_id = region.get("id", "unknown")
        if region_id != self._current_region_id:
            self._current_region_id = region_id
            self._turns_in_region = 0
        else:
            self._turns_in_region += 1

        # Select mode based on current situation
        mode = self._select_mode(state)
        self.current_mode = mode
        self.mode_history.append(mode)
        self.mode_stats[mode].used += 1

        # Execute the chosen mode
        if mode == SuperMode.BEATDOWN:
            decision = self._beatdown_mode(state)
        elif mode == SuperMode.CONTROL:
            decision = self._control_mode(state)
        elif mode == SuperMode.BRIDGE_SPAM:
            decision = self._bridge_spam_mode(state)
        else:  # SIEGE
            decision = self._siege_mode(state)

        # Apply pack modifiers (e.g., defensive bias, heal priority)
        decision = self._apply_modifiers(decision, state)

        # Update stats
        if decision.get("kind") != "wait":
            self.stats["total_actions"] += 1
            self.stats["successful_actions"] += 1

        return decision

    def _select_mode(self, state: GameState) -> SuperMode:
        """Decide which mode fits the current situation."""
        hp_ratio = state.hp_ratio()
        enemy_count = len(state.get_enemies())
        items_count = len(state.get_valid_items())
        connections_count = len(state.get_connections())
        alert = state.alert_gauge
        danger = self._calculate_danger(state)

        # Low HP → safe Siege mode
        if hp_ratio < 0.25:
            return SuperMode.SIEGE
        if hp_ratio < 0.40 and danger > 50:
            return SuperMode.SIEGE

        # High HP & many items → Beatdown (clear everything)
        if hp_ratio > 0.7 and items_count > 3 and alert < 5:
            return SuperMode.BEATDOWN
        if hp_ratio > 0.8 and enemy_count < 2:
            return SuperMode.BEATDOWN

        # Good HP & many connections → Bridge Spam (pressure)
        if hp_ratio > 0.6 and connections_count > 3 and alert < 7:
            return SuperMode.BRIDGE_SPAM
        if hp_ratio > 0.65 and enemy_count > 1:
            return SuperMode.BRIDGE_SPAM

        # Mid HP → Control (defensive, chip damage)
        if 0.4 < hp_ratio < 0.7:
            return SuperMode.CONTROL

        # Default fallback
        return SuperMode.CONTROL

    # ===================================================================
    # MODE IMPLEMENTATIONS
    # ===================================================================

    def _beatdown_mode(self, state: GameState) -> Dict:
        """Aggressive push – attack, loot, move forward."""
        enemy_action = self._attack_best_enemy(state)
        if enemy_action:
            return {"kind": "attack", "obj": enemy_action, "mode": "beatdown"}

        item_action = self._collect_best_item(state)
        if item_action:
            return {"kind": "pickup", "obj": item_action, "mode": "beatdown"}

        move_action = self._move_forward(state)
        if move_action:
            return {"kind": "move", "obj": move_action, "mode": "beatdown"}

        return {"kind": "wait", "mode": "beatdown"}

    def _control_mode(self, state: GameState) -> Dict:
        """Defensive – heal, pick off threats, safe loot."""
        heal_action = self._get_healing_action(state)
        if heal_action:
            return {"kind": "pickup", "obj": heal_action, "mode": "control"}

        enemy_action = self._attack_threat(state)
        if enemy_action:
            return {"kind": "attack", "obj": enemy_action, "mode": "control"}

        chip_action = self._chip_damage(state)
        if chip_action:
            return {"kind": "attack", "obj": chip_action, "mode": "control"}

        safe_item = self._safe_loot(state)
        if safe_item:
            return {"kind": "pickup", "obj": safe_item, "mode": "control"}

        return {"kind": "wait", "mode": "control"}

    def _bridge_spam_mode(self, state: GameState) -> Dict:
        """Constant pressure – fast loot, spam attacks, fast moves."""
        fast_item = self._fast_loot(state)
        if fast_item:
            return {"kind": "pickup", "obj": fast_item, "mode": "bridge_spam"}

        spam_action = self._spam_attack(state)
        if spam_action:
            return {"kind": "attack", "obj": spam_action, "mode": "bridge_spam"}

        fast_move = self._fast_move(state)
        if fast_move:
            return {"kind": "move", "obj": fast_move, "mode": "bridge_spam"}

        return {"kind": "wait", "mode": "bridge_spam"}

    def _siege_mode(self, state: GameState) -> Dict:
        """Safe, consistent – survive, safe loot, chip, retreat."""
        survival_action = self._get_survival_action(state)
        if survival_action:
            return {"kind": "pickup", "obj": survival_action, "mode": "siege"}

        safe_item = self._safe_loot(state)
        if safe_item:
            return {"kind": "pickup", "obj": safe_item, "mode": "siege"}

        chip_action = self._chip_damage(state)
        if chip_action:
            return {"kind": "attack", "obj": chip_action, "mode": "siege"}

        retreat_action = self._retreat_to_safety(state)
        if retreat_action:
            return {"kind": "move", "obj": retreat_action, "mode": "siege"}

        return {"kind": "wait", "mode": "siege"}

    # ===================================================================
    # ACTION HELPERS
    # ===================================================================

    def _attack_best_enemy(self, state: GameState) -> Optional[Dict]:
        """Attack the most valuable enemy (low HP, high priority)."""
        enemies = state.get_enemies()
        if not enemies:
            return None
        me = state.get_self()
        hp_ratio = state.hp_ratio()

        targetable = []
        for enemy in enemies:
            if not isinstance(enemy, dict):
                continue
            is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
            if is_guardian and hp_ratio < 0.5:
                continue

            enemy_hp = float(enemy.get("hp", 0))
            enemy_max_hp = float(enemy.get("maxHp", 1))
            enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
            distance = state._calculate_distance(me, enemy)

            # Score: low HP + close = high
            score = (1 - enemy_ratio) * 100 - distance * 2
            if enemy_ratio < 0.2:
                score += 50   # Kill bonus
            targetable.append((enemy, score))

        if not targetable:
            return None
        targetable.sort(key=lambda x: x[1], reverse=True)
        return targetable[0][0]

    def _collect_best_item(self, state: GameState) -> Optional[Dict]:
        """Pick up the closest valuable item."""
        items = state.get_valid_items()
        if not items:
            return None
        me = state.get_self()
        for item in items:
            if not isinstance(item, dict):
                continue
            distance = state._calculate_distance(me, item)
            if distance < 5:
                return item
        return None

    def _move_forward(self, state: GameState) -> Optional[Dict]:
        """Move to a safe, unvisited region."""
        if state.in_cave:
            logger.debug("🚫 _move_forward skipped: in cave")
            return None
        connections = state.get_connections()
        if not connections:
            return None
        safe = [c for c in connections if not c.get("insideDeathZone", False)]
        if safe:
            return max(safe, key=lambda c: c.get("safetyScore", 0))
        return None

    def _get_healing_action(self, state: GameState) -> Optional[Dict]:
        """Pickup healing item if HP is low."""
        hp_ratio = state.hp_ratio()
        if hp_ratio > 0.5:
            return None
        items = state.get_items()
        me = state.get_self()
        for item in items:
            if not isinstance(item, dict):
                continue
            heal = float(item.get("heal", item.get("healAmount", 0)))
            if heal > 0:
                distance = state._calculate_distance(me, item)
                if distance < 4:
                    item_id = item.get("instanceId") or item.get("id")
                    if state.is_item_valid(item_id):
                        return item
        return None

    def _attack_threat(self, state: GameState) -> Optional[Dict]:
        """Attack nearest threatening enemy (not guardian if risky)."""
        enemies = state.get_enemies()
        if not enemies:
            return None
        me = state.get_self()
        hp_ratio = state.hp_ratio()
        if hp_ratio < 0.35:
            return None

        threats = []
        for enemy in enemies:
            if not isinstance(enemy, dict):
                continue
            is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
            if is_guardian and hp_ratio < 0.5:
                continue
            distance = state._calculate_distance(me, enemy)
            enemy_hp = float(enemy.get("hp", 0))
            if enemy_hp > 0 and distance < 8:
                threats.append((enemy, distance, enemy_hp))
        if threats:
            threats.sort(key=lambda x: (x[1], x[2]))  # closest first, then lowest HP
            return threats[0][0]
        return None

    def _chip_damage(self, state: GameState) -> Optional[Dict]:
        """Attack low-HP enemies to finish them off."""
        enemies = state.get_enemies()
        if not enemies:
            return None
        me = state.get_self()

        low_hp_enemies = []
        for enemy in enemies:
            if not isinstance(enemy, dict):
                continue
            enemy_hp = float(enemy.get("hp", 0))
            enemy_max_hp = float(enemy.get("maxHp", 1))
            enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
            if enemy_ratio < 0.4:
                distance = state._calculate_distance(me, enemy)
                if distance < 10:
                    low_hp_enemies.append((enemy, distance))

        if low_hp_enemies:
            low_hp_enemies.sort(key=lambda x: x[1])
            return low_hp_enemies[0][0]

        # Fallback: attack nearest enemy if close enough
        nearest = min(enemies, key=lambda e: state._calculate_distance(me, e))
        distance = state._calculate_distance(me, nearest)
        if distance < 8:
            return nearest
        return None

    def _safe_loot(self, state: GameState) -> Optional[Dict]:
        """Pick up items that are not near enemies."""
        items = state.get_valid_items()
        if not items:
            return None
        me = state.get_self()
        enemies = state.get_enemies()

        # First pass: items far from enemies
        for item in items:
            if not isinstance(item, dict):
                continue
            distance = state._calculate_distance(me, item)
            if distance < 4:
                safe = True
                for enemy in enemies:
                    if not isinstance(enemy, dict):
                        continue
                    enemy_dist = state._calculate_distance(enemy, item)
                    if enemy_dist < 3:
                        safe = False
                        break
                if safe:
                    return item

        # Second pass: any close item
        for item in items:
            distance = state._calculate_distance(me, item)
            if distance < 5:
                return item
        return None

    def _fast_loot(self, state: GameState) -> Optional[Dict]:
        """Pick up the nearest item regardless of risk."""
        items = state.get_valid_items()
        if not items:
            return None
        me = state.get_self()
        nearest = None
        nearest_dist = 999
        for item in items:
            distance = state._calculate_distance(me, item)
            if distance < nearest_dist:
                nearest_dist = distance
                nearest = item
        if nearest_dist < 6:
            return nearest
        return None

    def _spam_attack(self, state: GameState) -> Optional[Dict]:
        """Attack nearest enemy if HP is okay, with cooldown."""
        if self._attack_cooldown > 0:
            self._attack_cooldown -= 1
            return None
        enemies = state.get_enemies()
        if not enemies:
            return None
        me = state.get_self()
        hp_ratio = state.hp_ratio()
        if hp_ratio > 0.4:
            nearest = min(enemies, key=lambda e: state._calculate_distance(me, e))
            distance = state._calculate_distance(me, nearest)
            if distance < 10:
                self._attack_cooldown = 1
                return nearest
        return None

    def _fast_move(self, state: GameState) -> Optional[Dict]:
        """Move quickly to a safe region."""
        if state.in_cave:
            logger.debug("🚫 _fast_move skipped: in cave")
            return None
        connections = state.get_connections()
        if not connections:
            return None
        safe = [c for c in connections if not c.get("insideDeathZone", False) and c.get("safetyScore", 0) > 0.5]
        if safe:
            return max(safe, key=lambda c: c.get("safetyScore", 0))
        return None

    def _get_survival_action(self, state: GameState) -> Optional[Dict]:
        """Prioritize healing; if HP critical, retreat."""
        heal = self._get_healing_action(state)
        if heal:
            return heal
        hp_ratio = state.hp_ratio()
        if hp_ratio < 0.3:
            connections = state.get_connections()
            safe = [c for c in connections if not c.get("insideDeathZone", False)]
            if safe:
                return max(safe, key=lambda c: c.get("safetyScore", 0))
        return None

    def _retreat_to_safety(self, state: GameState) -> Optional[Dict]:
        """Move to the safest adjacent region."""
        if state.in_cave:
            logger.debug("🚫 _retreat_to_safety skipped: in cave")
            return None
        connections = state.get_connections()
        if not connections:
            return None
        safe = [c for c in connections if not c.get("insideDeathZone", False) and c.get("safetyScore", 0) > 0.6]
        if safe:
            return max(safe, key=lambda c: c.get("safetyScore", 0))
        all_safe = [c for c in connections if not c.get("insideDeathZone", False)]
        if all_safe:
            return max(all_safe, key=lambda c: c.get("safetyScore", 0))
        return None

    def _calculate_danger(self, state: GameState) -> float:
        """Compute a danger score from 0-100."""
        hp_ratio = state.hp_ratio()
        enemy_count = len(state.get_enemies())
        alert = state.alert_gauge
        danger = (1 - hp_ratio) * 50 + enemy_count * 10 + (alert / 10) * 20
        return min(danger, 100)

    def _apply_modifiers(self, decision: Dict, state: GameState) -> Dict:
        """Adjust decision based on pack effects."""
        if not self._pack_modifiers:
            return decision

        modified = dict(decision)

        # Defensive pack → reduce aggressive actions
        if self._pack_modifiers.get("defensive"):
            if modified.get("kind") in ["attack", "explore"]:
                modified["score"] = modified.get("score", 0) * 0.7

        # Healing priority
        if self._pack_modifiers.get("heal_priority", 1.0) > 1.0:
            if modified.get("kind") == "pickup":
                heal = modified.get("obj", {}).get("heal", 0)
                if heal > 0:
                    modified["score"] = modified.get("score", 0) * self._pack_modifiers["heal_priority"]

        return modified

    def execute(self, decision: Dict) -> Optional[Dict]:
        """Convert decision to action payload."""
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
        """Reset internal state for a new game."""
        self._used_interactables.clear()
        self._attack_cooldown = 0
        self.turn = 0
        self.mode_history = []
        self._regions_cleared.clear()
        self._cave_attempts = 0
        for mode in self.mode_stats:
            self.mode_stats[mode] = ModeStats()
        self.stats = {k: 0 for k in self.stats}

    def get_stats(self) -> Dict:
        """Return mode usage and performance statistics."""
        total = sum(s.used for s in self.mode_stats.values())
        return {
            "mode_stats": {
                mode.value: {
                    "used": stats.used,
                    "success": stats.success,
                    "success_rate": (stats.success / max(stats.used, 1)) * 100,
                    "kills": stats.kills,
                    "items": stats.items_collected,
                    "survival": stats.survival_time
                }
                for mode, stats in self.mode_stats.items()
            },
            "current_mode": self.current_mode.value,
            "mode_history": [m.value for m in self.mode_history[-10:]],
            "total_actions": self.stats["total_actions"],
            "success_rate": (self.stats["successful_actions"] / max(self.stats["total_actions"], 1)) * 100,
            "kills": self.stats["kills"],
            "items_collected": self.stats["items_collected"],
            "regions_cleared": self.stats["regions_cleared"]
        }
