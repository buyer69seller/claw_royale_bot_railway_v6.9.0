# src/services/auth_service.py
"""Service untuk authentication dan login"""

import logging
from typing import Dict, Any, Optional

from ..client.rest_client import RestClient

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
        self._account: Optional[Dict] = None
    
    async def login(self) -> Dict[str, Any]:
        logger.info("🔐 Logging in to Claw Royale...")
        self._account = await self.rest.get_account()
        
        if not self._account:
            raise RuntimeError("Failed to get account info")
        
        logger.info(f"✅ Logged in as: {self._account.get('name')}")
        
        readiness = self._account.get("readiness", {})
        if not readiness.get("agentToken", False):
            logger.info("🔑 Agent token missing, attempting to register...")
            try:
                # Coba register token
                success = await self.rest.ensure_agent_token()
                if success:
                    # Refresh account untuk mendapatkan token terbaru
                    self._account = await self.rest.get_account()
                    logger.info("✅ Agent token registered successfully")
                else:
                    logger.warning("⚠️ Agent token registration returned failure, continuing with free mode")
            except Exception as e:
                # ❗ TIDAK DIBLOKIR – free mode tetap bisa berjalan
                logger.warning(f"⚠️ Agent token registration failed: {e}")
                logger.info("ℹ️ Continuing with free mode (agent token not strictly required for free rooms)")
        
        return self._account
    
    async def get_websocket_auth(self) -> Dict[str, str]:
        return {
            "Authorization": f"mr-auth {self.rest.api_key}",
            "X-Version": self.rest.version or "1.15.0"
        }
    
    def get_account(self) -> Optional[Dict]:
        return self._account
    
    def is_logged_in(self) -> bool:
        return self._account is not None
