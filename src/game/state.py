# src/game/state.py
"""Game state management dengan item tracking dan region tracking"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
import logging
import math
import json
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class GameState:
    game_id: Optional[str] = None
    entry_type: str = "free"
    agent_id: Optional[str] = None
    self_token: Optional[str] = None
    is_alive: bool = True
    can_act: bool = True
    in_cave: bool = False
    view: Dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    last_view_hash: int = 0
    is_finished: bool = False
    is_dead: bool = False
    survival_time: int = 0
    kills: int = 0
    hp: float = 0
    max_hp: float = 1
    rejected_count: int = 0
    last_rejected_action: Optional[str] = None
    
    # Item tracking
    attempted_items: Set[str] = field(default_factory=set)
    collected_items: Set[str] = field(default_factory=set)
    item_cache: Dict[str, Dict] = field(default_factory=dict)
    
    # Region tracking
    visited_regions: Set[str] = field(default_factory=set)
    region_visit_count: Dict[str, int] = field(default_factory=dict)
    current_region_id: Optional[str] = None
    
    # Ruin & Alert
    alert_gauge: int = 0
    alert_active: bool = False
    ruin_cache: Dict[str, Dict] = field(default_factory=dict)
    explored_ruins: Set[str] = field(default_factory=set)
    
    # Inventory
    inventory_items: Dict[str, Dict] = field(default_factory=dict)
    equipped_items: Dict[str, str] = field(default_factory=dict)
    
    def update_view(self, view_data: Dict, reason: str = "sync"):
        view_str = json.dumps(view_data, sort_keys=True)
        new_hash = hash(view_str)
        
        if new_hash == self.last_view_hash and reason == "action_rejected":
            self.rejected_count += 1
        else:
            self.rejected_count = 0
            self.last_view_hash = new_hash
        
        self.view = view_data
        self.turn += 1
        
        self_data = view_data.get("self", {})
        self.is_alive = self_data.get("isAlive", True)
        self.self_token = self_data.get("id")
        self.in_cave = self_data.get("inCave", False)
        
        self.hp = float(self_data.get("hp", self_data.get("currentHp", self_data.get("health", 0))))
        self.max_hp = float(self_data.get("maxHp", self_data.get("maxHealth", self_data.get("hp", 1))))
        
        if "survivalTime" in self_data:
            self.survival_time = self_data.get("survivalTime", 0)
        if "kills" in self_data:
            self.kills = self_data.get("kills", 0)
        
        self._update_item_cache(view_data)
        self._track_region(view_data)
    
    def _update_item_cache(self, view_data: Dict):
        region = view_data.get("currentRegion", {})
        items = region.get("items", [])
        
        if self.turn == 1:
            self.item_cache.clear()
            self.attempted_items.clear()
            self.collected_items.clear()
        
        current_item_ids = set()
        for item in items:
            if isinstance(item, dict):
                item_id = item.get("instanceId") or item.get("id")
                if item_id:
                    current_item_ids.add(item_id)
                    self.item_cache[item_id] = item
        
        for cached_id in list(self.item_cache.keys()):
            if cached_id not in current_item_ids:
                if cached_id not in self.collected_items:
                    self.collected_items.add(cached_id)
                del self.item_cache[cached_id]
        
        self.attempted_items = self.attempted_items - self.collected_items
    
    def _track_region(self, view_data: Dict):
        region = view_data.get("currentRegion", {})
        region_id = region.get("id")
        if region_id:
            self.current_region_id = region_id
            self.visited_regions.add(region_id)
            self.region_visit_count[region_id] = self.region_visit_count.get(region_id, 0) + 1
    
    def get_self(self) -> Dict:
        return self.view.get("self", {})
    
    def get_region(self) -> Dict:
        return self.view.get("currentRegion", {})
    
    def get_items(self) -> List[Dict]:
        region = self.get_region()
        return region.get("items", [])
    
    def get_interactables(self) -> List[Dict]:
        region = self.get_region()
        return region.get("interactables", [])
    
    def get_connections(self) -> List[Dict]:
        region = self.get_region()
        connections = region.get("connections", [])
        result = []
        for conn in connections:
            if isinstance(conn, str):
                result.append({"regionId": conn, "insideDeathZone": False, "safetyScore": 0.5})
            elif isinstance(conn, dict):
                result.append(conn)
        return result
    
    def get_enemies(self) -> List[Dict]:
        enemies = []
        for enemy in self.view.get("visibleAgents", []):
            if self._is_alive(enemy):
                enemies.append(enemy)
        for monster in self.view.get("visibleMonsters", []):
            if self._is_alive(monster):
                enemies.append(monster)
        return enemies
    
    def get_valid_items(self) -> List[Dict]:
        items = self.get_items()
        valid_items = []
        me = self.get_self()
        
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("instanceId") or item.get("id")
            if not item_id:
                continue
            if item_id in self.attempted_items or item_id in self.collected_items:
                continue
            try:
                distance = self._calculate_distance(me, item)
                if distance < 5:
                    valid_items.append(item)
            except Exception:
                continue
        
        valid_items.sort(key=lambda x: (
            -float(x.get("heal", x.get("healAmount", 0))),
            -float(x.get("value", x.get("rarityValue", 0)))
        ))
        return valid_items
    
    def get_cave_exit(self) -> Optional[Dict]:
        if not self.in_cave:
            return None
        for obj in self.get_interactables():
            if not isinstance(obj, dict):
                continue
            obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
            if "cave" in obj_type and obj.get("isExit", False):
                return obj
        return None
    
    def hp_ratio(self) -> float:
        return self.hp / max(self.max_hp, 1)
    
    def is_low_hp(self, threshold: float = 0.25) -> bool:
        return self.hp_ratio() < threshold
    
    def is_item_valid(self, item_id: str) -> bool:
        if not item_id:
            return False
        return item_id not in self.attempted_items and item_id not in self.collected_items
    
    def mark_item_attempted(self, item_id: str):
        if item_id:
            self.attempted_items.add(item_id)
    
    def mark_item_collected(self, item_id: str):
        if item_id:
            self.collected_items.add(item_id)
            self.attempted_items.add(item_id)
            if item_id in self.item_cache:
                del self.item_cache[item_id]
    
    def mark_dead(self):
        self.is_dead = True
        self.is_alive = False
        self.is_finished = True
        logger.info(f"💀 YOU DIED! Survival: {self.survival_time}, Kills: {self.kills}")
    
    def mark_finished(self):
        self.is_finished = True
        logger.info(f"🏆 Game finished. Survival: {self.survival_time}, Kills: {self.kills}")
    
    def is_region_visited(self, region_id: str) -> bool:
        return region_id in self.visited_regions
    
    def get_region_visit_count(self, region_id: str) -> int:
        return self.region_visit_count.get(region_id, 0)
    
    def update_alert_gauge(self, alert_data: Dict):
        self.alert_gauge = alert_data.get("alertGauge", 0)
        self.alert_active = alert_data.get("alertActive", False)
    
    def _calculate_distance(self, obj1: Dict, obj2: Dict) -> float:
        try:
            if obj1 is None or obj2 is None:
                return 999.0
            if isinstance(obj1, str):
                obj1 = {"x": 0, "y": 0}
            if isinstance(obj2, str):
                obj2 = {"x": 0, "y": 0}
            if isinstance(obj1, list):
                obj1 = obj1[0] if obj1 else {"x": 0, "y": 0}
            if isinstance(obj2, list):
                obj2 = obj2[0] if obj2 else {"x": 0, "y": 0}
            if not isinstance(obj1, dict) or not isinstance(obj2, dict):
                return 999.0
            
            x1 = float(obj1.get("x", obj1.get("position", {}).get("x", 0)))
            y1 = float(obj1.get("y", obj1.get("position", {}).get("y", 0)))
            x2 = float(obj2.get("x", obj2.get("position", {}).get("x", 0)))
            y2 = float(obj2.get("y", obj2.get("position", {}).get("y", 0)))
            return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
        except Exception:
            return 999.0
    
    @staticmethod
    def _is_alive(obj: Dict) -> bool:
        if not isinstance(obj, dict):
            return False
        return obj.get("isAlive", False) is True and obj.get("hp", 0) > 0
    
    def get_item_stats(self) -> Dict:
        return {
            "cache_size": len(self.item_cache),
            "attempted": len(self.attempted_items),
            "collected": len(self.collected_items),
            "valid_items": len(self.get_valid_items())
        }