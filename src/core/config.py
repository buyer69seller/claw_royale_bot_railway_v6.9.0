# src/core/config.py
"""Konfigurasi dari environment"""

import os
from dotenv import load_dotenv
from .constants import DEFAULT_ENTRY_TYPE, DEFAULT_PREFERRED_MODE, DEFAULT_ACTION_INTERVAL
from .exceptions import ConfigurationError

load_dotenv()

# Required
API_KEY = os.getenv("CLAW_API_KEY", "").strip()
if not API_KEY:
    raise ConfigurationError("CLAW_API_KEY is required")

# Strategy Mode
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "super_hybrid").lower()
VALID_STRATEGY_MODES = ["hybrid", "scan_clear", "hybrid_v7", "ai_auto_pilot", "competitive_v7", "super_hybrid"]
if STRATEGY_MODE not in VALID_STRATEGY_MODES:
    STRATEGY_MODE = "super_hybrid"

# Game
ENTRY_TYPE = os.getenv("ENTRY_TYPE", DEFAULT_ENTRY_TYPE).lower()
if ENTRY_TYPE not in ["free", "paid"]:
    raise ConfigurationError(f"Invalid ENTRY_TYPE: {ENTRY_TYPE}")

PREFERRED_MODE = os.getenv("PREFERRED_MODE", DEFAULT_PREFERRED_MODE).lower()
if PREFERRED_MODE not in ["offchain", "onchain"]:
    raise ConfigurationError(f"Invalid PREFERRED_MODE: {PREFERRED_MODE}")

ACTION_INTERVAL_SECONDS = float(os.getenv("ACTION_INTERVAL_SECONDS", str(DEFAULT_ACTION_INTERVAL)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# RL
RL_ENABLED = os.getenv("RL_ENABLED", "true").lower() in ["true", "1", "yes"]
RL_LEARNING_RATE = float(os.getenv("RL_LEARNING_RATE", "0.1"))
RL_EPSILON_START = float(os.getenv("RL_EPSILON_START", "1.0"))
RL_EPSILON_END = float(os.getenv("RL_EPSILON_END", "0.05"))

# Memory
MAX_KNOWLEDGE_HISTORY = int(os.getenv("MAX_KNOWLEDGE_HISTORY", "500"))
MAX_RL_MEMORY = int(os.getenv("MAX_RL_MEMORY", "1000"))