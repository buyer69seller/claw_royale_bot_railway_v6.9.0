# src/strategy/evaluators.py
"""Score evaluators"""

from typing import Dict
from ..core.constants import (
    SCORE_HEAL_BASE, SCORE_HEAL_HP_BONUS,
    SCORE_ATTACK_BASE, SCORE_ATTACK_HP_BONUS,
    SCORE_GUARDIAN_PENALTY, SCORE_ATTACK_KILL_BONUS,
    SCORE_SURVIVAL_BONUS,
    SCORE_LOOT_BASE, SCORE_LOOT_BONUS,
    SCORE_INTERACT_BASE,
    SCORE_EXPLORE_BASE,
    SCORE_MOVE_BASE
)

def num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def hp(obj: Dict) -> float:
    return num(obj.get("hp", obj.get("currentHp", obj.get("health", 0))))

def max_hp(obj: Dict) -> float:
    return max(1, num(obj.get("maxHp", obj.get("maxHealth", obj.get("hp", 1)))))

def alive(obj: Dict) -> bool:
    return obj.get("isAlive", False) is True and hp(obj) > 0

def heal_score(item: Dict, hp_ratio: float) -> float:
    heal_amount = num(item.get("heal", item.get("healAmount", 0)))
    if heal_amount > 0:
        return SCORE_HEAL_BASE + (1 - hp_ratio) * SCORE_HEAL_HP_BONUS
    return 0

def combat_score(enemy: Dict, hp_ratio: float) -> float:
    if not alive(enemy):
        return 0
    ratio = hp(enemy) / max_hp(enemy)
    score = SCORE_ATTACK_BASE + (1 - ratio) * SCORE_ATTACK_HP_BONUS
    if hp_ratio < 0.3:
        score -= (0.3 - hp_ratio) * 500
    if enemy.get("isGuardian", False) or str(enemy.get("kind", "")).lower() == "guardian":
        score -= SCORE_GUARDIAN_PENALTY
    if hp_ratio > 0.5 and hp(enemy) <= num(enemy.get("attack", enemy.get("atk", 0))):
        score += SCORE_ATTACK_KILL_BONUS
    score += SCORE_SURVIVAL_BONUS * hp_ratio
    return score

def loot_score(item: Dict) -> float:
    item_type = str(item.get("type", item.get("itemType", ""))).lower()
    value = num(item.get("value", item.get("rarityValue", 0)))
    score = SCORE_LOOT_BASE + value
    if any(k in item_type for k in ("weapon", "armor", "relic", "ep", "attack", "def")):
        score += SCORE_LOOT_BONUS
    return score

def interact_score(obj: Dict) -> float:
    obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
    if any(k in obj_type for k in ("medical", "supply", "cache", "watchtower")):
        return SCORE_INTERACT_BASE
    return 0

def explore_score(obj: Dict, region: Dict) -> float:
    obj_type = str(obj.get("type", obj.get("kind", ""))).lower()
    if "ruin" in obj_type:
        alert = num(region.get("alertGauge", 0))
        return SCORE_EXPLORE_BASE - max(0, alert - 6) * 80
    return 0

def move_score(connection: Dict, in_cave: bool = False) -> float:
    if in_cave:
        return -1000
    score = SCORE_MOVE_BASE
    if isinstance(connection, dict):
        score += num(connection.get("safetyScore", connection.get("zoneSafety", 0))) * 100
        if connection.get("insideDeathZone") is True:
            score -= 1000
    return score