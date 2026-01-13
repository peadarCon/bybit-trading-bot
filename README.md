# Bybit Trading Bot - SMA Crossover Strategy

A Python trading bot that uses Simple Moving Average (SMA) crossover strategy on Bybit testnet (paper trading).

## Features

- SMA crossover strategy (20/50 periods)
- Paper trading on Bybit testnet
- BTC/USDT trading pair
- 1-hour candle timeframe
- File-based logging of all trades and signals
- Configurable parameters

## Prerequisites

- Python 3.8 or higher
- Bybit testnet account with API keys

## Getting Bybit Testnet API Keys

1. Go to [Bybit Testnet](https://testnet.bybit.com/)
2. Create an account (separate from your main Bybit account)
3. After logging in, go to **Profile** > **API Management**
4. Click **Create New Key**
5. Select **System-generated API Keys**
6. Give it a name (e.g., "Trading Bot")
7. Set permissions:
   - Enable **Read-Write**
   - Enable **Trade** permissions
8. Complete verification and save your API Key and Secret

**Important:** Never share your API keys or commit them to version control!

## Installation

1. Navigate to the project folder:
   ```bash
   cd /Users/peadarconaghan/VSProjects/bybit-trading-bot
   ```

2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your API keys:
   - Open `config.py`
   - Replace `your_testnet_api_key_here` with your actual API key
   - Replace `your_testnet_api_secret_here` with your actual API secret

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `SYMBOL` | BTCUSDT | Trading pair |
| `SHORT_SMA_PERIOD` | 20 | Fast SMA period |
| `LONG_SMA_PERIOD` | 50 | Slow SMA period |
| `TIMEFRAME` | 60 | Candle interval (minutes) |
| `TRADE_QUANTITY` | 0.001 | BTC amount per trade |
| `CHECK_INTERVAL` | 60 | Seconds between checks |

## Usage

Run the bot:
```bash
python bot.py
```

Stop the bot: Press `Ctrl+C`

## How It Works

The bot uses the SMA crossover strategy:

1. **Buy Signal**: When the 20-period SMA crosses ABOVE the 50-period SMA
2. **Sell Signal**: When the 20-period SMA crosses BELOW the 50-period SMA

The bot checks for signals every 60 seconds and executes trades accordingly.

## Logs

All activity is logged to:
- Console output (real-time)
- `logs/trading_bot.log` (persistent)

## Project Structure

```
bybit-trading-bot/
├── bot.py           # Main trading bot
├── config.py        # Configuration settings
├── logger.py        # Logging utility
├── requirements.txt # Python dependencies
├── README.md        # This file
└── logs/
    └── trading_bot.log
```

## Disclaimer

This bot is for educational and paper trading purposes only. Do not use with real funds without thorough testing and understanding of the risks involved in cryptocurrency trading.
