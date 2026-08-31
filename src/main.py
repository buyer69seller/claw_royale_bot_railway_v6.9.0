# src/main.py
"""Entry point bot Claw Royale dengan Super Hybrid AI"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from .client.rest_client import RestClient
from .lifecycle.driver import Driver
from .core.config import API_KEY, STRATEGY_MODE
from .utils.logger import setup_logging
from .services.reward_service import RewardService
from .services.loadout_service import LoadoutService
from .services.inventory_service import InventoryService
from .utils.health import HealthServer
from .ai.knowledge import KnowledgeBase
from .core.constants import ensure_directories
from .services.auth_service import AuthService

health_server = None
driver_task = None
knowledge = None

STRATEGY_DESCRIPTIONS = {
    "hybrid": "🤖 Hybrid AI + RL - Adaptive decision making",
    "scan_clear": "📋 Scan & Clear - Collect all items, clear all enemies",
    "hybrid_v7": "🧠 Hybrid v7 - 3 Mode Strategy",
    "ai_auto_pilot": "🧠 AI Auto-Pilot - ML-based",
    "competitive_v7": "⚡ Competitive v7 - Heuristic priority",
    "super_hybrid": "🔥 SUPER HYBRID - 4 Mode Strategy (Beatdown + Control + Bridge Spam + Siege)"
}


async def shutdown(signal, loop):
    logger = logging.getLogger(__name__)
    logger.info(f"🛑 Received signal {signal}, shutting down...")
    if knowledge:
        knowledge.save()
    if health_server:
        await health_server.stop()
    if driver_task:
        driver_task.cancel()
        try:
            await driver_task
        except asyncio.CancelledError:
            pass
    loop.stop()


async def main():
    global health_server, driver_task, knowledge

    setup_logging()
    logger = logging.getLogger(__name__)

    ensure_directories()
    logger.info("📁 Directories ensured")

    if not API_KEY:
        logger.error("❌ CLAW_API_KEY not set!")
        sys.exit(1)

    logger.info("🦀 Starting Claw Royale Bot v6.1 - Super Hybrid AI")
    logger.info("=" * 60)
    logger.info(f"🧠 Strategy Mode: {STRATEGY_MODE.upper()}")
    logger.info(f"   📋 {STRATEGY_DESCRIPTIONS.get(STRATEGY_MODE, 'Unknown')}")
    logger.info("=" * 60)

    knowledge = KnowledgeBase()
    try:
        removed = knowledge.clear_old_data(days=30)
        if removed > 0:
            logger.info(f"🧹 Cleaned {removed} old knowledge entries")
    except Exception:
        pass

    insights = knowledge.get_insights()
    logger.info(f"📊 AI Knowledge:")
    logger.info(f"   - Win Rate: {insights['performance']['win_rate']*100:.1f}%")
    logger.info(f"   - Avg Survival: {insights['performance']['avg_survival']:.0f} turns")
    logger.info(f"   - Kills/Game: {insights['performance']['kills_per_game']:.1f}")
    logger.info(f"   - Success Rate: {insights['performance']['success_rate']*100:.1f}%")
    logger.info(f"   - Total Games: {insights['total_games']}")
    logger.info("=" * 60)

    health_server = HealthServer(port=8080)
    await health_server.start()
    logger.info("✅ Health server started on port 8080")

    async with RestClient(API_KEY) as rest:
        auth_service = AuthService(rest)
        try:
            account = await auth_service.login()
            logger.info("=" * 60)
            logger.info("✅ LOGIN SUCCESSFUL")
            logger.info(f"   Account: {account.get('name')}")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"❌ Login failed: {e}")
            sys.exit(1)

        try:
            reward_service = RewardService(rest)
            await reward_service.redeem_welcome_bundle()
        except Exception:
            pass

        try:
            loadout_service = LoadoutService(rest)
            if not await loadout_service.is_full_set():
                await loadout_service.optimize_loadout()
        except Exception:
            pass

        try:
            inventory_service = InventoryService(rest)
            result = await inventory_service.auto_equip_best()
            if result.get("changes"):
                logger.info(f"✅ Auto-equipped: {result['changes']}")
        except Exception:
            pass

        logger.info("=" * 60)
        logger.info("🚀 Starting Super Hybrid AI Auto-Pilot...")
        logger.info(f"🧠 Strategy: {STRATEGY_MODE.upper()}")
        logger.info("🎮 Ready to join games...")
        logger.info("=" * 60)

        driver = Driver(rest)
        driver.knowledge = knowledge
        driver.auth_service = auth_service
        driver.set_strategy_mode(STRATEGY_MODE)

        if health_server:
            health_server.set_driver(driver)

        driver_task = asyncio.create_task(driver.run())

        try:
            await driver_task
        except asyncio.CancelledError:
            logger.info("Driver task cancelled")


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)

    print("=" * 60)
    print("🦀 Claw Royale Bot v6.1 - Super Hybrid AI")
    print(f"🧠 Strategy: {STRATEGY_MODE.upper()}")
    print("=" * 60)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    finally:
        if knowledge:
            knowledge.save()
        loop.close()
        sys.exit(0)