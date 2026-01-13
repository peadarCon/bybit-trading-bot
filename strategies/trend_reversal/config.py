"""
Configuration for the Trend Reversal Strategy.
Buys red candles in an uptrend, expecting mean reversion.
"""

# Bybit API Configuration (Testnet)
API_KEY = "your_testnet_api_key_here"
API_SECRET = "your_testnet_api_secret_here"
USE_TESTNET = True

# Trading pair
SYMBOL = "BTCUSDT"
CATEGORY = "spot"

# Trend detection settings
TREND_SMA_PERIOD = 50        # SMA period to determine trend direction
TREND_LOOKBACK = 5           # Number of candles to confirm trend (SMA rising)

# Intraday settings
TIMEFRAME = "15"             # 15-minute candles for intraday trading

# Entry conditions
MIN_RED_CANDLE_PCT = 0.1     # Minimum red candle size (% drop) to trigger entry
MAX_RED_CANDLE_PCT = 2.0     # Maximum red candle size (avoid catching falling knives)

# Exit settings
TAKE_PROFIT_PCT = 0.5        # Take profit at 0.5% gain
STOP_LOSS_PCT = 1.0          # Stop loss at 1% loss
MAX_HOLD_CANDLES = 4         # Max candles to hold before exiting (1 hour on 15m)

# Risk management
TRADE_QUANTITY = 0.001       # Amount of BTC per trade
MAX_DAILY_TRADES = 10        # Maximum trades per day
CHECK_INTERVAL = 60          # Check every 60 seconds

# Logging
LOG_FILE = "logs/trend_reversal.log"
LOG_LEVEL = "INFO"
