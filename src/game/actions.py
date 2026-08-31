# src/game/actions.py
"""Action builder"""

from typing import Dict, Optional

class ActionBuilder:
    @staticmethod
    def pickup(item) -> Optional[Dict]:
        if not item:
            return None
        if isinstance(item, str):
            return {"type": "pickup", "itemInstanceId": item}
        if isinstance(item, dict):
            item_id = item.get("instanceId") or item.get("itemInstanceId") or item.get("id")
            if item_id:
                return {"type": "pickup", "itemInstanceId": item_id}
        return None
    
    @staticmethod
    def attack(target) -> Optional[Dict]:
        if not target:
            return None
        if isinstance(target, str):
            return {"type": "attack", "targetId": target}
        if isinstance(target, dict):
            target_id = target.get("agentId") or target.get("monsterId") or target.get("targetId") or target.get("id")
            if target_id:
                return {"type": "attack", "targetId": target_id}
        return None
    
    @staticmethod
    def interact(obj) -> Optional[Dict]:
        if not obj:
            return None
        obj_id = obj.get("interactableId") or obj.get("id")
        if obj_id:
            return {"type": "interact", "interactableId": obj_id}
        return None
    
    @staticmethod
    def explore(obj) -> Optional[Dict]:
        if not obj:
            return None
        obj_id = obj.get("interactableId") or obj.get("id")
        if obj_id:
            return {"type": "explore", "interactableId": obj_id}
        return None
    
    @staticmethod
    def move(target) -> Optional[Dict]:
        if not target:
            return None
        if isinstance(target, str):
            return {"type": "move", "regionId": target}
        if isinstance(target, dict):
            region_id = target.get("regionId")
            if region_id:
                return {"type": "move", "regionId": region_id}
        return None
    
    @staticmethod
    def use_item(item) -> Optional[Dict]:
        if not item:
            return None
        item_id = item.get("instanceId") or item.get("id")
        if item_id:
            return {"type": "use", "itemInstanceId": item_id}
        return None
    
    @staticmethod
    def use_item_by_id(item_id: str) -> Optional[Dict]:
        if item_id:
            return {"type": "use", "itemInstanceId": item_id}
        return None