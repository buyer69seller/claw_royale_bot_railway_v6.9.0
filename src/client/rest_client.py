# src/client/rest_client.py
"""REST API client"""

import aiohttp
import json
import logging
from typing import Optional, Dict, Any

from ..core.constants import BASE_API
from ..core.exceptions import AuthenticationError, VersionMismatchError, ClawRoyaleError

logger = logging.getLogger(__name__)

class RestClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._version: Optional[str] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
    
    @property
    def version(self) -> str:
        return self._version or "1.15.0"
    
    async def get_version(self) -> str:
        async with self._get("/version") as resp:
            data = await resp.json()
            self._version = data.get("version") or data.get("data", {}).get("version")
            return self._version
    
    async def get_account(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me")
    
    async def get_loadout(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me/loadout")
    
    async def equip_main_pack(self, pack_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/main", json={"packId": pack_id})
    
    async def equip_sub_pack(self, pack_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/sub", json={"packId": pack_id})
    
    async def equip_relic(self, relic_id: str) -> Dict:
        return await self._request("POST", "/accounts/me/loadout/relics", json={"relicId": relic_id})
    
    async def get_inventory(self) -> Dict[str, Any]:
        return await self._request("GET", "/accounts/me/inventory")
    
    async def redeem_code(self, code: str) -> Dict:
        return await self._request("POST", "/redeem", json={"code": code})
    
    async def _request(self, method: str, path: str, **kwargs) -> Dict:
        if not self._session:
            raise RuntimeError("Session not initialized")
        
        url = f"{BASE_API}{path}"
        headers = {
            "Authorization": f"mr-auth {self.api_key}",
            "X-Version": self._version or "1.15.0"
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        
        try:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 426:
                    raise VersionMismatchError(await resp.text())
                if resp.status == 401:
                    raise AuthenticationError("Invalid API key")
                if resp.status == 404:
                    return {}
                resp.raise_for_status()
                data = await resp.json()
                if not data.get("success", True):
                    error = data.get("error", {})
                    raise ClawRoyaleError(f"API Error: {error.get('code')} - {error.get('message')}")
                return data.get("data", {})
        except aiohttp.ClientError as e:
            logger.warning(f"Request failed: {e}")
            return {}
    
    def _get(self, path: str, **kwargs):
        return self._session.get(f"{BASE_API}{path}", headers=self._default_headers, **kwargs)
    
    @property
    def _default_headers(self) -> Dict:
        return {
            "Authorization": f"mr-auth {self.api_key}",
            "X-Version": self._version or "1.15.0"
        }