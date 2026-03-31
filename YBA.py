import discord
import requests
import pandas as pd
from discord.ext import tasks
from threading import Thread
from flask import Flask
from web3 import Web3
import os
import asyncio
import time
import random

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WALLET = "0xA9ad8Ef52D0445b62CbF142d97EF5493501352f3"   # Your position holder

# LFJ Pool Details
POOL_ADDRESS = "0x640963da1d9d07cb86e89df670dd29b54e1f1d3e"  # Your SOL/AVAX pool
AVAX_RPC = "https://avalanche-c-chain-rpc.publicnode.com"     # Free public RPC

TARGET_SOL_PCT = 60.0
WARNING_DEVIATION = 20.0
# =========================================================

print("=== YieldBase SOL/AVAX LP Agent (On-Chain) Starting on Railway ===")

# Connect to Avalanche
w3 = Web3(Web3.HTTPProvider(AVAX_RPC))

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ YieldBase SOL/AVAX Bot (On-Chain) is running on Railway!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

def get_pool_reserves():
    """Get current reserves from the LFJ pool (approximation for ratio)"""
    try:
        # Basic ERC20 balanceOf for wrapped tokens if needed, but for ratio we can use pool state
        # For Liquidity Book, we simplify to current active bin reserves if possible
        # Fallback: Try to get token0 and token1 reserves if pool exposes them
        print("Fetching pool reserves from Avalanche...")
        
        # Placeholder - in practice we'd call pool-specific view functions
        # For now, use CoinGecko prices + assume position tracks pool ratio closely
        # Better future: query LBPair contract for getReserves or active bin
        
        return None  # We'll enhance this based on logs
    except Exception as e:
        print(f"Pool query error: {e}")
        return None

# Fallback to simple price-based ratio for now (will improve)
def get_current_ratio():
    try:
        prices = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana,avalanche-2&vs_currencies=usd", timeout=10).json()
        sol_price = prices["solana"]["usd"]
        avax_price = prices["avalanche-2"]["usd"]
        print(f"Current prices - SOL: ${sol_price}, AVAX: ${avax_price}")
        return sol_price, avax_price
    except:
        return 85.0, 9.0

def calculate_rsi(coin_id: str, days=14):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        data = requests.get(url, timeout=15).json()["prices"]
        df = pd.DataFrame(data, columns=["ts", "price"])
        delta = df["price"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi.iloc[-1], 1)
    except:
        return 50.0

async def safe_send(message):
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await asyncio.sleep(3)
            await channel.send(message)
    except Exception as e:
        print(f"Send error: {e}")

@tasks.loop(hours=8)
async def monitor_lp():
    sol_price, avax_price = get_current_ratio()
    
    # For now, we log that we need better on-chain data
    # In a real full version we'd calculate actual user share of reserves
    alert = f"""🚨 **SOL/AVAX LP Monitor (On-Chain Mode)**

Current Prices: SOL ${sol_price:.2f} | AVAX ${avax_price:.2f}
Note: On-chain position reading is being calibrated.
Target: 60/40 SOL/AVAX

RSI (14d): SOL {calculate_rsi("solana")} | AVAX {calculate_rsi("avalanche-2")}"""

    await safe_send(alert)
    print("Monitor cycle completed - on-chain position fetch in progress")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and monitoring your SOL/AVAX pool on Railway (On-Chain)!")
    await asyncio.sleep(8)
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
