# src/services/reward_service.py
"""Service untuk mengelola reward dan redeem"""

import logging
from typing import Dict, Any

from ..client.rest_client import RestClient
from ..core.exceptions import ClawRoyaleError

logger = logging.getLogger(__name__)

class RewardService:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._redeemed_codes = set()
    
    async def redeem_welcome_bundle(self) -> bool:
        try:
            if "WELCOME" in self._redeemed_codes:
                return False
            result = await self.rest.redeem_code("WELCOME")
            if result:
                logger.info("🎁 Welcome bundle claimed!")
                self._redeemed_codes.add("WELCOME")
                return True
            return False
        except ClawRoyaleError as e:
            if "already redeemed" in str(e).lower() or "already claimed" in str(e).lower():
                self._redeemed_codes.add("WELCOME")
                return False
            logger.warning(f"Failed to redeem welcome bundle: {e}")
            return False
        except Exception as e:
            logger.warning(f"Welcome bundle not available: {e}")
            return False