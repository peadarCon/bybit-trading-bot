"""
Bybit Trading Bot - SMA Crossover Strategy
Paper trading bot using Bybit testnet.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
import pandas as pd
from pybit.unified_trading import HTTP

from strategies.sma_crossover.config import (
    API_KEY,
    API_SECRET,
    USE_TESTNET,
    SYMBOL,
    CATEGORY,
    SHORT_SMA_PERIOD,
    LONG_SMA_PERIOD,
    TIMEFRAME,
    TRADE_QUANTITY,
    CHECK_INTERVAL,
)
from logger import setup_logger, log_trade, log_signal  # shared logger from root


class TradingBot:
    def __init__(self):
        self.logger = setup_logger()
        self.position = None  # None, "long", or "short"
        self.last_signal = None

        # Initialize Bybit client
        self.logger.info("Initializing Bybit connection...")
        self.client = HTTP(
            testnet=USE_TESTNET,
            api_key=API_KEY,
            api_secret=API_SECRET,
        )
        self.logger.info(f"Connected to Bybit {'Testnet' if USE_TESTNET else 'Mainnet'}")
        self.logger.info(f"Trading pair: {SYMBOL}")
        self.logger.info(f"Strategy: SMA Crossover ({SHORT_SMA_PERIOD}/{LONG_SMA_PERIOD})")

    def get_klines(self, limit=100):
        """Fetch historical kline/candlestick data."""
        try:
            response = self.client.get_kline(
                category=CATEGORY,
                symbol=SYMBOL,
                interval=TIMEFRAME,
                limit=limit,
            )

            if response["retCode"] != 0:
                self.logger.error(f"Error fetching klines: {response['retMsg']}")
                return None

            # Convert to DataFrame
            data = response["result"]["list"]
            df = pd.DataFrame(
                data,
                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
            )

            # Convert types
            df["close"] = pd.to_numeric(df["close"])
            df["timestamp"] = pd.to_numeric(df["timestamp"])

            # Sort by timestamp (oldest first)
            df = df.sort_values("timestamp").reset_index(drop=True)

            return df

        except Exception as e:
            self.logger.error(f"Exception fetching klines: {e}")
            return None

    def calculate_sma(self, df):
        """Calculate short and long SMAs."""
        df["sma_short"] = df["close"].rolling(window=SHORT_SMA_PERIOD).mean()
        df["sma_long"] = df["close"].rolling(window=LONG_SMA_PERIOD).mean()
        return df

    def get_signal(self, df):
        """
        Determine trading signal based on SMA crossover.
        Returns: "buy", "sell", or None
        """
        if len(df) < LONG_SMA_PERIOD + 1:
            return None

        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Check for crossover
        # Buy signal: short SMA crosses above long SMA
        if (previous["sma_short"] <= previous["sma_long"] and
                current["sma_short"] > current["sma_long"]):
            return "buy"

        # Sell signal: short SMA crosses below long SMA
        if (previous["sma_short"] >= previous["sma_long"] and
                current["sma_short"] < current["sma_long"]):
            return "sell"

        return None

    def place_order(self, side):
        """Place a market order."""
        try:
            self.logger.info(f"Placing {side.upper()} order for {TRADE_QUANTITY} {SYMBOL}...")

            response = self.client.place_order(
                category=CATEGORY,
                symbol=SYMBOL,
                side=side.capitalize(),  # "Buy" or "Sell"
                orderType="Market",
                qty=str(TRADE_QUANTITY),
            )

            if response["retCode"] != 0:
                self.logger.error(f"Order failed: {response['retMsg']}")
                return False

            order_id = response["result"]["orderId"]
            self.logger.info(f"Order placed successfully. Order ID: {order_id}")
            return True

        except Exception as e:
            self.logger.error(f"Exception placing order: {e}")
            return False

    def get_current_price(self):
        """Get the current market price."""
        try:
            response = self.client.get_tickers(
                category=CATEGORY,
                symbol=SYMBOL,
            )

            if response["retCode"] != 0:
                return None

            return float(response["result"]["list"][0]["lastPrice"])

        except Exception as e:
            self.logger.error(f"Error getting price: {e}")
            return None

    def run(self):
        """Main bot loop."""
        self.logger.info("=" * 50)
        self.logger.info("Starting Trading Bot")
        self.logger.info("=" * 50)

        while True:
            try:
                # Get market data
                df = self.get_klines()
                if df is None:
                    self.logger.warning("Failed to get market data, retrying...")
                    time.sleep(CHECK_INTERVAL)
                    continue

                # Calculate indicators
                df = self.calculate_sma(df)

                # Get current values
                current_price = self.get_current_price()
                if current_price is None:
                    time.sleep(CHECK_INTERVAL)
                    continue

                current_short_sma = df.iloc[-1]["sma_short"]
                current_long_sma = df.iloc[-1]["sma_long"]

                self.logger.debug(
                    f"Price: ${current_price:,.2f} | "
                    f"SMA{SHORT_SMA_PERIOD}: ${current_short_sma:,.2f} | "
                    f"SMA{LONG_SMA_PERIOD}: ${current_long_sma:,.2f}"
                )

                # Check for trading signal
                signal = self.get_signal(df)

                if signal and signal != self.last_signal:
                    log_signal(
                        self.logger,
                        signal.upper(),
                        current_short_sma,
                        current_long_sma,
                        current_price
                    )

                    # Execute trade based on signal
                    if signal == "buy" and self.position != "long":
                        if self.place_order("Buy"):
                            log_trade(self.logger, "BUY", current_price, TRADE_QUANTITY, SYMBOL)
                            self.position = "long"
                            self.last_signal = signal

                    elif signal == "sell" and self.position != "short":
                        if self.place_order("Sell"):
                            log_trade(self.logger, "SELL", current_price, TRADE_QUANTITY, SYMBOL)
                            self.position = "short"
                            self.last_signal = signal

                # Wait before next check
                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
