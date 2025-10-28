"""
Main entry point for crypto arbitrage system
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

from core.engine import ArbitrageEngine
from config.settings import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/logs/arbitrage.log')
    ]
)

logger = logging.getLogger(__name__)


class ArbitrageBot:
    def __init__(self):
        self.engine = None
        self.shutdown_event = asyncio.Event()
        
    async def start(self):
        """Start the arbitrage bot"""
        try:
            # Load configuration
            config = load_config()
            
            # Initialize engine
            self.engine = ArbitrageEngine(config)
            
            # Setup signal handlers
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            
            # Run engine
            await self.engine.run()
            
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise
            
    async def stop(self):
        """Stop the bot gracefully"""
        logger.info("Shutdown signal received")
        if self.engine:
            await self.engine.shutdown()
        self.shutdown_event.set()


async def main():
    """Main entry point"""
    bot = ArbitrageBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
