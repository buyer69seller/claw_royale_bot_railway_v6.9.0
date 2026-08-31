# src/core/constants.py
"""Konstanta global untuk bot"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Runtime directories
CACHE_DIR = os.getenv("CACHE_DIR", str(BASE_DIR / "runtime_cache"))
LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
KNOWLEDGE_PATH = os.getenv("KNOWLEDGE_PATH", str(BASE_DIR / "knowledge.json"))

def ensure_directories():
    for d in [CACHE_DIR, LOG_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)

# API Endpoints
BASE_API = "https://cdn.clawroyale.ai/api"
JOIN_WS = "wss://cdn.clawroyale.ai/ws/join"
AGENT_WS = "wss://cdn.clawroyale.ai/ws/agent"

# Default values
DEFAULT_ENTRY_TYPE = "free"
DEFAULT_PREFERRED_MODE = "offchain"
DEFAULT_ACTION_INTERVAL = 0.25
ACTION_INTERVAL_SECONDS = float(os.getenv("ACTION_INTERVAL_SECONDS", str(DEFAULT_ACTION_INTERVAL)))

# Retry
MIN_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
RETRY_BACKOFF_MULTIPLIER = 2.0

# Strategy scoring
SCORE_HEAL_BASE = 900
SCORE_HEAL_HP_BONUS = 700
SCORE_ATTACK_BASE = 550
SCORE_ATTACK_HP_BONUS = 600
SCORE_GUARDIAN_PENALTY = 300
SCORE_ATTACK_KILL_BONUS = 150
SCORE_SURVIVAL_BONUS = 200
SCORE_LOOT_BASE = 300
SCORE_LOOT_BONUS = 250
SCORE_INTERACT_BASE = 520
SCORE_EXPLORE_BASE = 380
SCORE_MOVE_BASE = 250
SCORE_CAVE_EXIT = 1000

# Document cache
DOCS_TO_CACHE = [
    "/skill.md", "/openapi.yaml",
    "/references/actions.md", "/references/game-loop.md",
    "/references/combat-items.md", "/references/game-systems.md",
    "/references/api-summary.md", "/references/errors.md"
]

# AI Constants
AI_LEARNING_RATE = 0.1
AI_CONFIDENCE_THRESHOLD = 0.6
AI_RISK_THRESHOLD = 0.7

# Pack Data
MAIN_ONLY_PACKS = ["Scout", "Assassin"]
SUB_CAPABLE_PACKS = [
    "Moltz Expert", "Item Expert", "Goliath", "Thorns",
    "Ruin Expert", "Berserker", "Double Attack",
    "Heart of the Giant", "Bomber", "Trail Ward",
    "Ranged", "Sword Master", "Duelist", "Raider",
    "Last Stand", "Iron Heart", "Sunflame Cloak", "Pickpocket"
]

# Relic Slots
RELIC_SLOTS = {"Ruby": 0, "Emerald": 1, "Sapphire": 2}
RELIC_AFFIX_PRIORITY = {
    "atk": 5, "item_atk": 4, "max_hp": 4,
    "def": 3, "hp_regen": 3, "explore": 2
}