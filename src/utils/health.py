# src/utils/health.py
"""Health check server untuk monitoring"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self, port: int = 8080):
        self.port = port
        self._runner = None
        self._site = None
        self._running = False
        self._start_time = time.time()
        self._driver_ref = None
    
    async def start(self, driver=None):
        if not HAS_AIOHTTP:
            return
        if self._running:
            return
        
        self._driver_ref = driver
        
        try:
            app = web.Application()
            app.router.add_get('/health', self._health_handler)
            app.router.add_get('/ready', self._ready_handler)
            app.router.add_get('/metrics', self._metrics_handler)
            app.router.add_get('/stats', self._stats_handler)
            app.router.add_get('/dashboard', self._dashboard_handler)
            
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, '0.0.0.0', self.port)
            await self._site.start()
            self._running = True
            logger.info(f"Health server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
    
    async def stop(self):
        if self._runner and self._running:
            await self._runner.cleanup()
            self._running = False
    
    @staticmethod
    async def _health_handler(request):
        return web.Response(text="OK", status=200)
    
    @staticmethod
    async def _ready_handler(request):
        return web.Response(text="READY", status=200)
    
    async def _metrics_handler(self, request):
        uptime = int(time.time() - self._start_time)
        metrics = {"uptime": uptime, "status": "running", "timestamp": int(time.time())}
        
        if self._driver_ref:
            try:
                perf = self._driver_ref.get_performance() if hasattr(self._driver_ref, 'get_performance') else {}
                metrics.update({
                    "game_count": perf.get("game_count", 0),
                    "total_actions": perf.get("total_actions", 0),
                    "success_rate": perf.get("success_rate", 0),
                    "is_in_game": perf.get("is_in_game", False)
                })
                hybrid_stats = perf.get("hybrid_stats", {})
                if hybrid_stats:
                    metrics["hybrid_ai"] = hybrid_stats
                rl_stats = perf.get("rl_stats", {})
                if rl_stats:
                    metrics["rl"] = rl_stats
            except Exception as e:
                logger.debug(f"Failed to get driver metrics: {e}")
        
        return web.json_response(metrics)
    
    async def _stats_handler(self, request):
        uptime = int(time.time() - self._start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        
        stats = {"bot": {"status": "running", "uptime": f"{hours}h {minutes}m {seconds}s", "version": "6.1.0"}}
        
        if self._driver_ref:
            try:
                perf = self._driver_ref.get_performance() if hasattr(self._driver_ref, 'get_performance') else {}
                stats["game"] = {
                    "games_played": perf.get("game_count", 0),
                    "total_actions": perf.get("total_actions", 0),
                    "success_rate": f"{perf.get('success_rate', 0) * 100:.1f}%",
                    "is_in_game": perf.get("is_in_game", False)
                }
            except Exception as e:
                logger.debug(f"Failed to get driver stats: {e}")
        
        return web.json_response(stats)
    
    async def _dashboard_handler(self, request):
        return web.Response(text=self._format_dashboard_html(), content_type="text/html")
    
    def _format_dashboard_html(self) -> str:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Claw Royale Bot - Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
                .container { max-width: 800px; margin: 0 auto; }
                .card { background: #16213e; border-radius: 10px; padding: 20px; margin: 10px 0; border-left: 4px solid #0f3460; }
                .card h2 { margin: 0 0 10px 0; color: #e94560; }
                .stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1a1a3e; }
                .stat .label { color: #aaa; }
                .stat .value { color: #fff; font-weight: bold; }
                .green { color: #4ade80; }
                .yellow { color: #facc15; }
                .red { color: #f87171; }
                .header { text-align: center; padding: 20px 0; }
                .header h1 { color: #e94560; margin: 0; }
                .header p { color: #888; margin: 5px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🦀 Claw Royale Bot</h1>
                    <p>v6.1 - Super Hybrid AI</p>
                </div>
                <div class="card">
                    <h2>🤖 Bot Status</h2>
                    <div class="stat"><span class="label">Status</span><span class="value green">Running</span></div>
                    <div class="stat"><span class="label">Version</span><span class="value">6.1.0</span></div>
                    <div class="stat"><span class="label">Engine</span><span class="value">Super Hybrid AI</span></div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def set_driver(self, driver):
        self._driver_ref = driver