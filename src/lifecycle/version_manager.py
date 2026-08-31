# src/lifecycle/version_manager.py
"""Version manager dengan ETag-based caching dan lock"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional

from ..core.constants import BASE_API, CACHE_DIR, DOCS_TO_CACHE

logger = logging.getLogger(__name__)

class VersionManager:
    def __init__(self, key: str):
        self.key = key
        self.version: Optional[str] = None
        self.cache = Path(CACHE_DIR)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._initialized = False  # Flag untuk mencegah refresh berulang

        # Load meta dari file
        self.meta = {}
        meta_file = self.cache / "etag_meta.json"
        if meta_file.exists():
            try:
                self.meta = json.loads(meta_file.read_text())
                logger.debug(f"📂 Loaded meta from cache: {len(self.meta)} entries")
            except Exception as e:
                logger.warning(f"Failed to load meta cache: {e}")
                self.meta = {}
        else:
            logger.debug("📂 No existing meta cache, starting fresh")

    async def ensure_current(self, session):
        """Memastikan dokumentasi versi terbaru, hanya refresh jika perlu."""
        async with self._lock:
            # 1. Cek versi dari server
            async with session.get(
                f"{BASE_API}/version",
                headers={"X-API-Key": self.key},
                timeout=15
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                new_version = data.get("version") or data.get("data", {}).get("version")

            # 2. Jika versi sama dan semua dokumen sudah di-cache, skip refresh
            if (self.meta.get("_version") == new_version and
                all(doc in self.meta for doc in DOCS_TO_CACHE) and
                self._initialized):
                self.version = new_version
                logger.debug(f"📦 Using cached docs for version {new_version}")
                return

            # 3. Versi berubah atau cache tidak lengkap → refresh
            logger.info(f"🔄 Version changed to {new_version}, refreshing docs...")
            self.version = new_version
            self._initialized = True

            # 4. Refresh dokumen yang diperlukan
            headers = {"X-API-Key": self.key, "X-Version": self.version}
            for path in DOCS_TO_CACHE:
                h = dict(headers)
                etag = self.meta.get(path, {}).get("etag")
                if etag:
                    h["If-None-Match"] = etag

                try:
                    async with session.get(
                        f"{BASE_API}{path}",
                        headers=h,
                        timeout=20
                    ) as resp:
                        if resp.status == 304:
                            # Dokumen tidak berubah, pertahankan cache
                            continue
                        if resp.status != 200:
                            logger.warning(f"Doc {path} HTTP {resp.status}")
                            continue

                        # Dokumen baru atau berubah
                        body = await resp.text()
                        cache_path = path.lstrip("/").replace("/", "__")
                        (self.cache / cache_path).write_text(body)
                        self.meta[path] = {
                            "etag": resp.headers.get("ETag"),
                            "version": self.version
                        }
                        logger.debug(f"✅ Updated doc: {path}")

                except Exception as e:
                    logger.warning(f"Doc {path} refresh failed: {e}")

            # 5. Simpan metadata terbaru
            self.meta["_version"] = self.version
            try:
                (self.cache / "etag_meta.json").write_text(
                    json.dumps(self.meta, indent=2)
                )
            except Exception as e:
                logger.warning(f"Failed to save meta cache: {e}")
