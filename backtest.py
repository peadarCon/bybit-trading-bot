"""
Backtesting module for the Bybit Trading Bot.
Simulates trading from a historical start date to see how the strategy would have performed.
No API keys required - uses public market data.
"""

import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from config import (
    SYMBOL,
    CATEGORY,
    SHORT_SMA_PERIOD,
    LONG_SMA_PERIOD,
    TIMEFRAME,
    TRADE_QUANTITY,
)


class Backtester:
    def __init__(self, start_date: str, end_date: str = None, initial_balance: float = 10000.0):
        """
        Initialize the backtester.

        Args:
            start_date: Start date for backtest (format: "YYYY-MM-DD")
            end_date: End date for backtest (format: "YYYY-MM-DD"), defaults to now
            initial_balance: Starting USD balance for simulation
        """
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        self.initial_balance = initial_balance

        # Trading state
        self.balance = initial_balance
        self.position = None  # None or "long"
        self.position_size = 0.0  # Amount of asset held
        self.entry_price = 0.0

        # Trade history
        self.trades = []

        # Connect to Bybit public API (no auth needed for market data)
        self.client = HTTP(testnet=False)

        print(f"Backtester initialized")
        print(f"  Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"  Symbol: {SYMBOL}")
        print(f"  Strategy: SMA Crossover ({SHORT_SMA_PERIOD}/{LONG_SMA_PERIOD})")
        print(f"  Initial balance: ${initial_balance:,.2f}")
        print()

    def fetch_historical_data(self):
        """Fetch all historical kline data for the backtest period."""
        print("Fetching historical data...")

        all_data = []
        start_ts = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)

        # We need extra data before start_date to calculate SMAs
        warmup_periods = LONG_SMA_PERIOD + 10
        interval_ms = int(TIMEFRAME) * 60 * 1000
        warmup_start_ts = start_ts - (warmup_periods * interval_ms)

        current_ts = warmup_start_ts

        while current_ts < end_ts:
            try:
                response = self.client.get_kline(
                    category=CATEGORY,
                    symbol=SYMBOL,
                    interval=TIMEFRAME,
                    start=current_ts,
                    limit=1000,
                )

                if response["retCode"] != 0:
                    print(f"Error fetching data: {response['retMsg']}")
                    break

                data = response["result"]["list"]
                if not data:
                    break

                all_data.extend(data)

                # Move to next batch (data comes newest first)
                timestamps = [int(d[0]) for d in data]
                current_ts = max(timestamps) + interval_ms

                print(f"  Fetched {len(all_data)} candles...")

            except Exception as e:
                print(f"Error: {e}")
                break

        if not all_data:
            return None

        # Convert to DataFrame
        df = pd.DataFrame(
            all_data,
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
        )

        # Convert types
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        df["timestamp"] = pd.to_numeric(df["timestamp"])

        # Remove duplicates and sort
        df = df.drop_duplicates(subset=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Convert timestamp to datetime
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Filter to include warmup period + backtest period
        df = df[df["timestamp"] <= end_ts]

        print(f"  Total candles: {len(df)}")
        print(f"  Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
        print()

        return df

    def calculate_sma(self, df):
        """Calculate SMAs on the dataframe."""
        df["sma_short"] = df["close"].rolling(window=SHORT_SMA_PERIOD).mean()
        df["sma_long"] = df["close"].rolling(window=LONG_SMA_PERIOD).mean()
        return df

    def simulate_buy(self, price, timestamp):
        """Simulate a buy order."""
        # Use configured trade quantity or max affordable
        cost = TRADE_QUANTITY * price
        if cost > self.balance:
            # Buy what we can afford
            self.position_size = self.balance / price
            cost = self.balance
        else:
            self.position_size = TRADE_QUANTITY

        self.balance -= cost
        self.position = "long"
        self.entry_price = price

        self.trades.append({
            "timestamp": timestamp,
            "type": "BUY",
            "price": price,
            "quantity": self.position_size,
            "balance_after": self.balance,
            "portfolio_value": self.balance + (self.position_size * price)
        })

        return True

    def simulate_sell(self, price, timestamp):
        """Simulate a sell order."""
        if self.position != "long" or self.position_size == 0:
            return False

        proceeds = self.position_size * price
        profit = proceeds - (self.position_size * self.entry_price)
        profit_pct = (price - self.entry_price) / self.entry_price * 100

        self.balance += proceeds

        self.trades.append({
            "timestamp": timestamp,
            "type": "SELL",
            "price": price,
            "quantity": self.position_size,
            "profit": profit,
            "profit_pct": profit_pct,
            "balance_after": self.balance,
            "portfolio_value": self.balance
        })

        self.position = None
        self.position_size = 0
        self.entry_price = 0

        return True

    def run(self):
        """Run the backtest simulation."""
        # Fetch historical data
        df = self.fetch_historical_data()
        if df is None:
            print("Failed to fetch historical data")
            return

        # Calculate indicators
        df = self.calculate_sma(df)

        # Find the index where our actual backtest starts (after warmup)
        start_ts = int(self.start_date.timestamp() * 1000)
        backtest_start_idx = df[df["timestamp"] >= start_ts].index[0]

        print("Running simulation...")
        print("-" * 60)

        last_signal = None

        # Iterate through each candle from start date
        for i in range(backtest_start_idx, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i - 1]

            # Skip if SMAs not yet calculated
            if pd.isna(current["sma_short"]) or pd.isna(current["sma_long"]):
                continue

            price = current["close"]
            timestamp = current["datetime"]

            # Check for crossover signals
            signal = None

            # Buy signal: short SMA crosses above long SMA
            if (previous["sma_short"] <= previous["sma_long"] and
                    current["sma_short"] > current["sma_long"]):
                signal = "buy"

            # Sell signal: short SMA crosses below long SMA
            if (previous["sma_short"] >= previous["sma_long"] and
                    current["sma_short"] < current["sma_long"]):
                signal = "sell"

            # Execute trades
            if signal and signal != last_signal:
                if signal == "buy" and self.position != "long":
                    self.simulate_buy(price, timestamp)
                    print(f"{timestamp} | BUY  @ ${price:,.2f} | Balance: ${self.balance:,.2f}")
                    last_signal = signal

                elif signal == "sell" and self.position == "long":
                    self.simulate_sell(price, timestamp)
                    trade = self.trades[-1]
                    print(f"{timestamp} | SELL @ ${price:,.2f} | Profit: ${trade['profit']:+,.2f} ({trade['profit_pct']:+.2f}%)")
                    last_signal = signal

        # Close any open position at the end
        if self.position == "long":
            final_price = df.iloc[-1]["close"]
            self.simulate_sell(final_price, df.iloc[-1]["datetime"])
            trade = self.trades[-1]
            print(f"{trade['timestamp']} | SELL (closing) @ ${final_price:,.2f} | Profit: ${trade['profit']:+,.2f}")

        print("-" * 60)
        print()

        # Print results
        self.print_results()

    def print_results(self):
        """Print backtest results and statistics."""
        print("=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)

        # Calculate statistics
        total_trades = len([t for t in self.trades if t["type"] == "SELL"])

        if total_trades == 0:
            print("No trades executed during backtest period.")
            return

        winning_trades = [t for t in self.trades if t["type"] == "SELL" and t.get("profit", 0) > 0]
        losing_trades = [t for t in self.trades if t["type"] == "SELL" and t.get("profit", 0) <= 0]

        total_profit = sum(t.get("profit", 0) for t in self.trades if t["type"] == "SELL")
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        avg_win = sum(t["profit"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t["profit"] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        final_value = self.balance
        total_return = (final_value - self.initial_balance) / self.initial_balance * 100

        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Symbol: {SYMBOL}")
        print()
        print(f"Initial Balance:  ${self.initial_balance:,.2f}")
        print(f"Final Balance:    ${final_value:,.2f}")
        print(f"Total Return:     ${total_profit:+,.2f} ({total_return:+.2f}%)")
        print()
        print(f"Total Trades:     {total_trades}")
        print(f"Winning Trades:   {len(winning_trades)}")
        print(f"Losing Trades:    {len(losing_trades)}")
        print(f"Win Rate:         {win_rate:.1f}%")
        print()
        print(f"Average Win:      ${avg_win:+,.2f}")
        print(f"Average Loss:     ${avg_loss:+,.2f}")

        if losing_trades and avg_loss != 0:
            profit_factor = abs(sum(t["profit"] for t in winning_trades) / sum(t["profit"] for t in losing_trades)) if losing_trades else float('inf')
            print(f"Profit Factor:    {profit_factor:.2f}")

        print("=" * 60)

        # Print trade log
        print("\nTRADE LOG:")
        print("-" * 60)
        for trade in self.trades:
            if trade["type"] == "BUY":
                print(f"{trade['timestamp']} | BUY  | {trade['quantity']:.6f} @ ${trade['price']:,.2f}")
            else:
                print(f"{trade['timestamp']} | SELL | {trade['quantity']:.6f} @ ${trade['price']:,.2f} | P&L: ${trade.get('profit', 0):+,.2f}")


def main():
    """Run a backtest with command line arguments or defaults."""
    import sys

    # Default: backtest the last 7 days
    if len(sys.argv) >= 2:
        start_date = sys.argv[1]
    else:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    if len(sys.argv) >= 3:
        end_date = sys.argv[2]
    else:
        end_date = None  # defaults to now

    initial_balance = 10000.0
    if len(sys.argv) >= 4:
        initial_balance = float(sys.argv[3])

    print("=" * 60)
    print("BYBIT TRADING BOT - BACKTESTER")
    print("=" * 60)
    print()

    backtester = Backtester(
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance
    )
    backtester.run()


if __name__ == "__main__":
    main()
