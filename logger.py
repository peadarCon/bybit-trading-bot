"""
Logging utility for the trading bot.
"""

import logging
import os
from datetime import datetime
from config import LOG_FILE, LOG_LEVEL


def setup_logger():
    """Set up and return a configured logger instance."""

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create logger
    logger = logging.getLogger("TradingBot")
    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper()))

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def log_trade(logger, action, price, quantity, symbol):
    """Log a trade execution."""
    logger.info(f"TRADE | {action} | {quantity} {symbol} @ ${price:,.2f}")


def log_signal(logger, signal_type, short_sma, long_sma, current_price):
    """Log a trading signal."""
    logger.info(
        f"SIGNAL | {signal_type} | Price: ${current_price:,.2f} | "
        f"SMA({short_sma:.2f}) / SMA({long_sma:.2f})"
    )
