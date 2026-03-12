
# 🐳 Polymarket Whale Alert Bot

A bot that detects large trades on Polymarket and sends instant Telegram notifications.

## Features
- Monitors top 100 markets by volume
- Detects trades above $5,000
- Checks every 30 seconds
- Sends Telegram alerts with wallet address and market link

## Installation
pip install requests schedule

## Configuration
Open polymarket_whale_bot.py and set:
- TELEGRAM_BOT_TOKEN — get from @BotFather on Telegram
- TELEGRAM_CHAT_ID — get from @userinfobot on Telegram
- MIN_TRADE_SIZE_USD — minimum trade size to alert (default: $5000)
- MAX_MARKETS — number of markets to monitor (default: 100)

## Usage
python polymarket_whale_bot.py

## How It Works
The bot fetches the top markets from Polymarket's Gamma API, then checks
for new large trades every 30 seconds using the Data API. When a trade
above the threshold is detected, it sends a Telegram notification with
the market name, direction, amount, price, wallet address, and a direct link.
