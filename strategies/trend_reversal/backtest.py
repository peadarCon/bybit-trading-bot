"""
Backtesting module for the Trend Reversal Strategy.
Buys red candles in an uptrend, expecting mean reversion to green.
No API keys required - uses public market data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
from strategies.trend_reversal.config import (
    SYMBOL,
    CATEGORY,
    TREND_SMA_PERIOD,
    TREND_LOOKBACK,
    TIMEFRAME,
    MIN_RED_CANDLE_PCT,
    MAX_RED_CANDLE_PCT,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    MAX_HOLD_CANDLES,
    TRADE_QUANTITY,
    MAX_DAILY_TRADES,
)


class TrendReversalBacktester:
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
        self.position = None
        self.position_size = 0.0
        self.entry_price = 0.0
        self.entry_candle_idx = 0
        self.daily_trades = 0
        self.current_day = None

        # Trade history
        self.trades = []

        # Connect to Bybit public API
        self.client = HTTP(testnet=False)

        print("=" * 60)
        print("TREND REVERSAL STRATEGY - BACKTESTER")
        print("=" * 60)
        print()
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Symbol: {SYMBOL}")
        print(f"Timeframe: {TIMEFRAME}m candles")
        print()
        print("Strategy Rules:")
        print(f"  - Trend: Price above {TREND_SMA_PERIOD} SMA, SMA rising for {TREND_LOOKBACK} candles")
        print(f"  - Entry: Red candle between {MIN_RED_CANDLE_PCT}% and {MAX_RED_CANDLE_PCT}% drop")
        print(f"  - Take Profit: {TAKE_PROFIT_PCT}%")
        print(f"  - Stop Loss: {STOP_LOSS_PCT}%")
        print(f"  - Max Hold: {MAX_HOLD_CANDLES} candles")
        print(f"  - Max Daily Trades: {MAX_DAILY_TRADES}")
        print()
        print(f"Initial balance: ${initial_balance:,.2f}")
        print()

    def fetch_historical_data(self):
        """Fetch all historical kline data for the backtest period."""
        print("Fetching historical data...")

        all_data = []
        start_ts = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)

        # Extra data for SMA warmup
        warmup_periods = TREND_SMA_PERIOD + TREND_LOOKBACK + 10
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

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        df["timestamp"] = pd.to_numeric(df["timestamp"])

        df = df.drop_duplicates(subset=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[df["timestamp"] <= end_ts]

        print(f"  Total candles: {len(df)}")
        print(f"  Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
        print()

        return df

    def calculate_indicators(self, df):
        """Calculate trend indicators."""
        # SMA for trend
        df["sma"] = df["close"].rolling(window=TREND_SMA_PERIOD).mean()

        # SMA slope (is it rising?)
        df["sma_prev"] = df["sma"].shift(1)
        df["sma_rising"] = df["sma"] > df["sma_prev"]

        # Count consecutive rising SMAs
        df["sma_rising_count"] = 0
        count = 0
        for i in range(len(df)):
            if df.iloc[i]["sma_rising"]:
                count += 1
            else:
                count = 0
            df.iloc[i, df.columns.get_loc("sma_rising_count")] = count

        # Candle color and size
        df["is_red"] = df["close"] < df["open"]
        df["candle_pct"] = ((df["open"] - df["close"]) / df["open"] * 100).clip(lower=0)

        # Is in uptrend?
        df["in_uptrend"] = (df["close"] > df["sma"]) & (df["sma_rising_count"] >= TREND_LOOKBACK)

        return df

    def is_valid_entry(self, row):
        """Check if current candle is a valid entry signal."""
        if not row["in_uptrend"]:
            return False

        if not row["is_red"]:
            return False

        if row["candle_pct"] < MIN_RED_CANDLE_PCT:
            return False

        if row["candle_pct"] > MAX_RED_CANDLE_PCT:
            return False

        return True

    def simulate_buy(self, price, timestamp, candle_idx):
        """Simulate a buy order."""
        cost = TRADE_QUANTITY * price
        if cost > self.balance:
            self.position_size = self.balance / price
            cost = self.balance
        else:
            self.position_size = TRADE_QUANTITY

        self.balance -= cost
        self.position = "long"
        self.entry_price = price
        self.entry_candle_idx = candle_idx

        self.trades.append({
            "timestamp": timestamp,
            "type": "BUY",
            "price": price,
            "quantity": self.position_size,
            "balance_after": self.balance,
        })

        return True

    def simulate_sell(self, price, timestamp, exit_reason):
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
            "exit_reason": exit_reason,
            "balance_after": self.balance,
        })

        self.position = None
        self.position_size = 0
        self.entry_price = 0
        self.entry_candle_idx = 0

        return True

    def check_exit_conditions(self, row, candle_idx):
        """Check if we should exit the position."""
        if self.position != "long":
            return None, None

        current_price = row["close"]
        high_price = row["high"]
        low_price = row["low"]

        # Calculate targets
        take_profit_price = self.entry_price * (1 + TAKE_PROFIT_PCT / 100)
        stop_loss_price = self.entry_price * (1 - STOP_LOSS_PCT / 100)

        # Check stop loss first (worst case)
        if low_price <= stop_loss_price:
            return stop_loss_price, "STOP_LOSS"

        # Check take profit
        if high_price >= take_profit_price:
            return take_profit_price, "TAKE_PROFIT"

        # Check time-based exit
        candles_held = candle_idx - self.entry_candle_idx
        if candles_held >= MAX_HOLD_CANDLES:
            return current_price, "TIME_EXIT"

        return None, None

    def run(self):
        """Run the backtest simulation."""
        df = self.fetch_historical_data()
        if df is None:
            print("Failed to fetch historical data")
            return

        df = self.calculate_indicators(df)

        # Find backtest start index
        start_ts = int(self.start_date.timestamp() * 1000)
        backtest_start_idx = df[df["timestamp"] >= start_ts].index[0]

        print("Running simulation...")
        print("-" * 60)

        for i in range(backtest_start_idx, len(df)):
            row = df.iloc[i]
            timestamp = row["datetime"]
            current_day = timestamp.date()

            # Reset daily trade counter
            if current_day != self.current_day:
                self.current_day = current_day
                self.daily_trades = 0

            # Check exit conditions first if in position
            if self.position == "long":
                exit_price, exit_reason = self.check_exit_conditions(row, i)
                if exit_price is not None:
                    self.simulate_sell(exit_price, timestamp, exit_reason)
                    trade = self.trades[-1]
                    emoji = "✓" if trade["profit"] > 0 else "✗"
                    print(f"{timestamp} | SELL @ ${exit_price:,.2f} | {exit_reason} | P&L: ${trade['profit']:+,.2f} ({trade['profit_pct']:+.2f}%) {emoji}")

            # Check entry conditions if not in position
            if self.position is None and self.daily_trades < MAX_DAILY_TRADES:
                if self.is_valid_entry(row):
                    entry_price = row["close"]
                    self.simulate_buy(entry_price, timestamp, i)
                    self.daily_trades += 1
                    print(f"{timestamp} | BUY  @ ${entry_price:,.2f} | Red candle: -{row['candle_pct']:.2f}% | SMA: ${row['sma']:,.2f}")

        # Close any open position
        if self.position == "long":
            final_price = df.iloc[-1]["close"]
            self.simulate_sell(final_price, df.iloc[-1]["datetime"], "END_OF_TEST")
            trade = self.trades[-1]
            print(f"{trade['timestamp']} | SELL @ ${final_price:,.2f} | END_OF_TEST | P&L: ${trade['profit']:+,.2f}")

        print("-" * 60)
        print()

        self.print_results()

    def print_results(self):
        """Print backtest results and statistics."""
        print("=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)

        sell_trades = [t for t in self.trades if t["type"] == "SELL"]
        total_trades = len(sell_trades)

        if total_trades == 0:
            print("No trades executed during backtest period.")
            return

        winning_trades = [t for t in sell_trades if t.get("profit", 0) > 0]
        losing_trades = [t for t in sell_trades if t.get("profit", 0) <= 0]

        total_profit = sum(t.get("profit", 0) for t in sell_trades)
        win_rate = len(winning_trades) / total_trades * 100

        avg_win = sum(t["profit"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t["profit"] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        final_value = self.balance
        total_return = (final_value - self.initial_balance) / self.initial_balance * 100

        # Exit reason breakdown
        exit_reasons = {}
        for t in sell_trades:
            reason = t.get("exit_reason", "UNKNOWN")
            if reason not in exit_reasons:
                exit_reasons[reason] = {"count": 0, "profit": 0}
            exit_reasons[reason]["count"] += 1
            exit_reasons[reason]["profit"] += t.get("profit", 0)

        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Symbol: {SYMBOL} ({TIMEFRAME}m candles)")
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

        if losing_trades:
            total_wins = sum(t["profit"] for t in winning_trades)
            total_losses = abs(sum(t["profit"] for t in losing_trades))
            profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
            print(f"Profit Factor:    {profit_factor:.2f}")

        print()
        print("Exit Breakdown:")
        for reason, data in sorted(exit_reasons.items()):
            print(f"  {reason}: {data['count']} trades, ${data['profit']:+,.2f}")

        print("=" * 60)


def main():
    """Run a backtest with command line arguments or defaults."""
    import sys

    if len(sys.argv) >= 2:
        start_date = sys.argv[1]
    else:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    if len(sys.argv) >= 3:
        end_date = sys.argv[2]
    else:
        end_date = None

    initial_balance = 10000.0
    if len(sys.argv) >= 4:
        initial_balance = float(sys.argv[3])

    backtester = TrendReversalBacktester(
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance
    )
    backtester.run()


if __name__ == "__main__":
    main()
