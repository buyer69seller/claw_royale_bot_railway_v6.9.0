# src/services/loadout_service.py
"""Service untuk manajemen loadout"""

import logging
from typing import Dict, Any, Optional, List

from ..client.rest_client import RestClient
from ..core.constants import RELIC_AFFIX_PRIORITY, RELIC_SLOTS, INVENTORY_CAPS

logger = logging.getLogger(__name__)

class LoadoutService:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._current_loadout = None
    
    async def get_current_loadout(self) -> Dict[str, Any]:
        if self._current_loadout:
            return self._current_loadout
        try:
            loadout = await self.rest.get_loadout()
            self._current_loadout = loadout
            return loadout
        except Exception as e:
            logger.warning(f"Could not get loadout: {e}")
            return {}
    
    async def is_full_set(self) -> bool:
        loadout = await self.get_current_loadout()
        has_main = bool(loadout.get("mainPack"))
        has_sub = bool(loadout.get("subPack"))
        relics = loadout.get("relics", [])
        return has_main and has_sub and len(relics) >= 3
    
    async def get_best_relics(self, count: int = 3) -> List[Dict]:
        inventory = await self.rest.get_inventory()
        relics = inventory.get("relics", [])
        if not relics:
            return []
        
        scored_relics = []
        for relic in relics:
            score = self._score_relic(relic)
            slot = self._get_relic_slot(relic)
            scored_relics.append({
                "relic": relic,
                "score": score,
                "slot": slot,
                "affix_count": len(relic.get("affixes", []))
            })
        
        scored_relics.sort(key=lambda x: (x["score"], x["affix_count"]), reverse=True)
        best = scored_relics[:count]
        return [r["relic"] for r in best]
    
    def _score_relic(self, relic: Dict) -> float:
        affixes = relic.get("affixes", [])
        tier = relic.get("tier", 0)
        score = tier * 10
        
        for affix in affixes:
            stat = affix.get("stat", "")
            value = affix.get("value", 0)
            priority = RELIC_AFFIX_PRIORITY.get(stat, 1)
            if value > 0:
                score += value * priority * 1.5
            else:
                score += value * priority * 0.5
        
        affix_count = len(affixes)
        if affix_count >= 3:
            score *= 1.3
        elif affix_count >= 2:
            score *= 1.15
        
        return max(score, -100)
    
    def _get_relic_slot(self, relic: Dict) -> int:
        name = relic.get("name", "")
        for gem_name, slot in RELIC_SLOTS.items():
            if gem_name in name:
                return slot
        return 0
    
    async def optimize_loadout(self) -> Dict[str, Any]:
        try:
            current = await self.get_current_loadout()
            best_relics = await self.get_best_relics(3)
            result = {"changes": [], "current": current}
            
            current_relic_ids = [r.get("id") for r in current.get("relics", [])]
            for relic in best_relics:
                if relic.get("id") not in current_relic_ids:
                    await self.rest.equip_relic(relic["id"])
                    result["changes"].append(f"Relic: {relic.get('name', 'unknown')}")
            
            self._current_loadout = None
            await self.get_current_loadout()
            return result
        except Exception as e:
            logger.debug(f"Loadout optimization skipped: {e}")
            return {"error": str(e), "changes": []}