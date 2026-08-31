# src/strategy/scan_clear.py
"""Scan & Clear Strategy - Ambil SEMUA item, bunuh SEMUA musuh, pindah region"""

import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

from ..game.state import GameState
from ..game.actions import ActionBuilder

logger = logging.getLogger(__name__)

@dataclass
class RegionStatus:
    region_id: str
    turn_entered: int = 0
    items_collected: List[str] = field(default_factory=list)
    enemies_cleared: List[str] = field(default_factory=list)
    is_complete: bool = False
    items_count: int = 0
    enemies_count: int = 0


class ScanClearStrategy:
    """
    Scan & Clear Strategy:
    - Scan inventory → ambil item terbaik (healing > weapon > relic > pack > other)
    - Clear enemies → serang musuh terlemah terdekat (kecuali guardian jika HP rendah)
    - Pindah ke region baru yang belum dikunjungi jika semua item/enemy sudah dibersihkan
    - Menghindari death zone
    """
    def __init__(self):
        self.action_builder = ActionBuilder()
        self.current_region: Optional[RegionStatus] = None
        self.visited_regions: Set[str] = set()
        self.max_turns_per_region = 10
        self.turn = 0
        self.region_counter = 0
        self.stats = {
            "regions_cleared": 0,
            "items_collected": 0,
            "enemies_killed": 0,
            "turns_spent": 0
        }
        # Untuk exit cave fallback
        self._cave_attempts = 0

    def reset(self):
        self.current_region = None
        self.visited_regions.clear()
        self.turn = 0
        self.region_counter = 0
        self.stats = {
            "regions_cleared": 0,
            "items_collected": 0,
            "enemies_killed": 0,
            "turns_spent": 0
        }
        self._cave_attempts = 0

    def decide(self, state: GameState) -> Dict[str, Any]:
        self.turn += 1
        self.stats["turns_spent"] += 1

        if not state.is_alive:
            return {"kind": "dead", "score": -1e9}

        # ----- HANDLING CAVE -----
        if state.in_cave:
            self._cave_attempts += 1
            logger.debug(f"🕳️ ScanClear: In cave (attempt {self._cave_attempts})")

            # 1. Cari exit resmi
            exit_obj = state.get_cave_exit()
            if exit_obj:
                logger.info("🚪 ScanClear: Exiting cave via detected exit")
                self._cave_attempts = 0
                return {"kind": "interact", "obj": exit_obj}

            # 2. Fallback: coba interact dengan objek pertama jika sudah beberapa turn
            if self._cave_attempts > 3:
                interactables = state.get_interactables()
                if interactables:
                    logger.warning("⚠️ ScanClear: No exit found, trying first interactable")
                    self._cave_attempts = 0
                    return {"kind": "interact", "obj": interactables[0]}

            # 3. Terakhir, wait agar tidak kena penolakan move
            logger.warning("⛔ ScanClear: In cave but no exit found – waiting")
            return {"kind": "wait"}
        else:
            # Reset counter saat keluar gua
            self._cave_attempts = 0
        # --------------------------------

        region = state.get_region()
        region_id = region.get("id", "unknown")

        if region_id != (self.current_region.region_id if self.current_region else None):
            self._enter_new_region(region_id, state)

        # Step 1: Scan Inventory
        item_action = self._scan_inventory(state)
        if item_action:
            self.stats["items_collected"] += 1
            logger.info(f"📦 SCAN & CLEAR: Collecting item")
            return {"kind": "pickup", "obj": item_action}

        # Step 2: Clear Enemies
        enemy_action = self._clear_enemies(state)
        if enemy_action:
            self.stats["enemies_killed"] += 1
            logger.info(f"⚔️ SCAN & CLEAR: Attacking enemy")
            return {"kind": "attack", "obj": enemy_action}

        # Step 3: Move to next region
        if self.current_region and self.current_region.turn_entered > self.max_turns_per_region:
            logger.info(f"🚪 SCAN & CLEAR: Moving to next region (timeout)")
            move_action = self._move_to_next_region(state)
            if move_action:
                return {"kind": "move", "obj": move_action}

        move_action = self._move_to_next_region(state)
        if move_action:
            return {"kind": "move", "obj": move_action}

        return {"kind": "wait"}

    def _enter_new_region(self, region_id: str, state: GameState):
        self.visited_regions.add(region_id)
        self.region_counter += 1
        items = state.get_items()
        enemies = state.get_enemies()
        self.current_region = RegionStatus(
            region_id=region_id,
            turn_entered=self.turn,
            items_count=len(items),
            enemies_count=len(enemies)
        )
        logger.info(f"🗺️ SCAN & CLEAR: Entered region {region_id[:8]} ({len(items)} items, {len(enemies)} enemies)")

    def _scan_inventory(self, state: GameState) -> Optional[Dict]:
        items = state.get_items()
        if not items:
            return None

        me = state.get_self()

        # Prioritaskan: healing → weapon → relic → pack → other
        healing_items = []
        weapon_items = []
        relic_items = []
        pack_items = []
        other_items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("instanceId") or item.get("id")
            if not item_id or not state.is_item_valid(item_id):
                continue
            try:
                distance = state._calculate_distance(me, item)
                if distance > 5:
                    continue
            except Exception:
                continue

            item_type = str(item.get("type", item.get("itemType", ""))).lower()
            heal = float(item.get("heal", item.get("healAmount", 0)))

            if heal > 0:
                healing_items.append(item)
            elif "weapon" in item_type:
                weapon_items.append(item)
            elif "relic" in item_type:
                relic_items.append(item)
            elif "pack" in item_type:
                pack_items.append(item)
            else:
                other_items.append(item)

        all_items = healing_items + weapon_items + relic_items + pack_items + other_items
        for item in all_items:
            item_id = item.get("instanceId") or item.get("id")
            if item_id:
                state.mark_item_attempted(item_id)
                return item

        return None

    def _clear_enemies(self, state: GameState) -> Optional[Dict]:
        enemies = state.get_enemies()
        if not enemies:
            return None

        me = state.get_self()
        hp_ratio = state.hp_ratio()

        if hp_ratio < 0.4:
            return None

        targetable = []
        for enemy in enemies:
            if not isinstance(enemy, dict):
                continue
            is_guardian = enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian"
            if is_guardian and hp_ratio < 0.6:
                continue
            enemy_hp = float(enemy.get("hp", 0))
            enemy_max_hp = float(enemy.get("maxHp", 1))
            enemy_ratio = enemy_hp / max(enemy_max_hp, 1)
            try:
                distance = state._calculate_distance(me, enemy)
            except Exception:
                continue
            priority_score = (1 - enemy_ratio) * 100 - distance * 2
            if enemy_ratio < 0.2:
                priority_score += 50
            if is_guardian:
                priority_score -= 80
            targetable.append((enemy, priority_score))

        if not targetable:
            return None

        targetable.sort(key=lambda x: x[1], reverse=True)
        return targetable[0][0]

    def _move_to_next_region(self, state: GameState) -> Optional[Dict]:
        # CEK CAVE: jika di dalam gua, jangan pindah
        if state.in_cave:
            logger.debug("🚫 _move_to_next_region skipped: in cave")
            return None

        connections = state.get_connections()
        if not connections:
            return None

        safe_connections = []
        for conn in connections:
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            if conn.get("insideDeathZone", False):
                continue
            region_id = conn.get("regionId")
            if region_id not in self.visited_regions:
                safe_connections.append(conn)

        if safe_connections:
            return max(safe_connections, key=lambda c: c.get("safetyScore", 0))

        # Jika semua region sudah dikunjungi, cari yang paling aman
        safe_all = []
        for conn in connections:
            if isinstance(conn, str):
                conn = {"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5}
            elif not isinstance(conn, dict):
                continue
            if not conn.get("insideDeathZone", False):
                safe_all.append(conn)

        if safe_all:
            return max(safe_all, key=lambda c: c.get("safetyScore", 0))

        return None
