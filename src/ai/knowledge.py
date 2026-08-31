# src/ai/knowledge.py
"""Knowledge Base - Belajar dari pengalaman dengan memory limit"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import datetime

from ..core.constants import KNOWLEDGE_PATH

logger = logging.getLogger(__name__)

class KnowledgeBase:
    MAX_HISTORY = 500
    MAX_PATTERNS = 100
    
    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or KNOWLEDGE_PATH)
        self.data = self._load()
        self.session_id = datetime.datetime.now().isoformat()
        self._session_count = 0
    
    def _load(self) -> Dict[str, Any]:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    if len(data.get("history", [])) > self.MAX_HISTORY:
                        data["history"] = data["history"][-self.MAX_HISTORY:]
                    return data
            except Exception as e:
                logger.warning(f"Failed to load knowledge: {e}")
        return self._default_knowledge()
    
    def _default_knowledge(self) -> Dict[str, Any]:
        return {
            "patterns": {"dangerous_situations": [], "good_opportunities": [], "failed_actions": [], "successful_actions": []},
            "stats": {"total_games": 0, "games_won": 0, "total_actions": 0, "successful_actions": 0, "kills": 0, "deaths": 0, "avg_survival": 0},
            "learned_weights": {"heal_value": 1.0, "attack_value": 1.0, "loot_value": 1.0, "explore_value": 1.0, "move_value": 1.0},
            "history": []
        }
    
    def save(self):
        self._cleanup()
        try:
            compact_data = self._compact_data()
            with open(self.storage_path, 'w') as f:
                json.dump(compact_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge: {e}")
    
    def _cleanup(self):
        if len(self.data.get("history", [])) > self.MAX_HISTORY:
            removed = len(self.data["history"]) - self.MAX_HISTORY
            self.data["history"] = self.data["history"][-self.MAX_HISTORY:]
        
        for key in self.data.get("patterns", {}):
            if len(self.data["patterns"][key]) > self.MAX_PATTERNS:
                self.data["patterns"][key] = self.data["patterns"][key][-self.MAX_PATTERNS:]
    
    def _compact_data(self) -> Dict[str, Any]:
        return {
            "patterns": self.data.get("patterns", {}),
            "stats": self.data.get("stats", {}),
            "learned_weights": self.data.get("learned_weights", {}),
            "history": self.data.get("history", [])[-self.MAX_HISTORY:],
            "last_updated": datetime.datetime.now().isoformat(),
            "total_entries": len(self.data.get("history", []))
        }
    
    async def record_decision(self, decision, perceived, analysis):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "session": self.session_id,
            "decision": {
                "action_type": decision.action_type,
                "target_id": decision.target_id,
                "confidence": decision.confidence,
                "expected_value": decision.expected_value
            },
            "context": {
                "hp_ratio": perceived.hp_ratio,
                "in_cave": perceived.in_cave,
                "enemy_count": len(perceived.enemies),
                "danger_level": perceived.danger_level,
                "opportunity_score": perceived.opportunity_score,
                "turn": perceived.turn
            },
            "analysis": {
                "threat_level": analysis["threat_level"]["level"],
                "battle_potential": analysis["battle_potential"]["potential"],
                "strategy": analysis["survival_strategy"]["primary"]
            }
        }
        self.data["history"].append(entry)
        self.data["stats"]["total_actions"] += 1
        self._session_count += 1
        if len(self.data["history"]) % 50 == 0:
            self.save()
    
    def record_outcome(self, outcome: str, details: Dict = None):
        self.data["stats"]["total_games"] += 1
        if outcome == "win":
            self.data["stats"]["games_won"] += 1
        elif outcome == "death":
            self.data["stats"]["deaths"] += 1
        if details:
            self.data["stats"]["kills"] += details.get("kills", 0)
            total_games = self.data["stats"]["total_games"]
            avg = self.data["stats"]["avg_survival"]
            survival = details.get("survival_time", 0)
            self.data["stats"]["avg_survival"] = (avg * (total_games - 1) + survival) / total_games
        self.save()
    
    def get_insights(self) -> Dict[str, Any]:
        stats = self.data["stats"]
        return {
            "performance": {
                "win_rate": stats["games_won"] / max(stats["total_games"], 1),
                "avg_survival": stats["avg_survival"],
                "kills_per_game": stats["kills"] / max(stats["total_games"], 1),
                "success_rate": stats["successful_actions"] / max(stats["total_actions"], 1)
            },
            "weights": self.data["learned_weights"],
            "pattern_count": {k: len(v) for k, v in self.data["patterns"].items()},
            "total_games": stats["total_games"],
            "memory": {
                "history_entries": len(self.data.get("history", [])),
                "max_history": self.MAX_HISTORY,
                "usage_percent": (len(self.data.get("history", [])) / self.MAX_HISTORY) * 100
            }
        }
    
    def clear_old_data(self, days: int = 30):
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        original_count = len(self.data.get("history", []))
        self.data["history"] = [h for h in self.data.get("history", []) if h.get("timestamp", "") > cutoff_str]
        removed = original_count - len(self.data["history"])
        if removed > 0:
            self.save()
        return removed