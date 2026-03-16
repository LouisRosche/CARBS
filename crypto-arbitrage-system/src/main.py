"""
Main entry point for crypto arbitrage system

DEPRECATED: This module is a compatibility wrapper.
Please use advanced_main.py directly for the full-featured bot:
    python -m src.advanced_main

Or use the CLI:
    carbs start --mode paper
"""
import warnings
import logging

logger = logging.getLogger(__name__)

# Issue deprecation warning
warnings.warn(
    "main.py is deprecated. Use advanced_main.py for the full-featured bot. "
    "Run: python -m src.advanced_main",
    DeprecationWarning,
    stacklevel=2
)


def main():
    """
    Main entry point - redirects to advanced_main

    This maintains backward compatibility while encouraging
    migration to the full-featured advanced_main.
    """
    logger.warning(
        "main.py is deprecated. Redirecting to advanced_main.py. "
        "Please update your scripts to use: python -m src.advanced_main"
    )

    # Import and run advanced_main
    from .advanced_main import main as advanced_main
    import asyncio

    asyncio.run(advanced_main())


if __name__ == "__main__":
    main()
