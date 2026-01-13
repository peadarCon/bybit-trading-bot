"""
Configuration settings for the Bybit trading bot.
"""

# Bybit API Configuration (Testnet)
# Get your testnet API keys from: https://testnet.bybit.com/
API_KEY = "your_testnet_api_key_here"
API_SECRET = "your_testnet_api_secret_here"

# Use testnet (paper trading) - set to False for live trading (NOT RECOMMENDED without thorough testing)
USE_TESTNET = True

# Trading pair configuration
SYMBOL = "BTCUSDT"
CATEGORY = "spot"  # spot, linear (USDT perpetual), inverse

# Strategy settings
SHORT_SMA_PERIOD = 20  # Fast moving average
LONG_SMA_PERIOD = 50   # Slow moving average
TIMEFRAME = "60"       # Candle interval in minutes (60 = 1 hour)

# Trading settings
TRADE_QUANTITY = 0.001  # Amount of BTC to trade per order
CHECK_INTERVAL = 60     # How often to check for signals (in seconds)

# Logging settings
LOG_FILE = "logs/trading_bot.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
