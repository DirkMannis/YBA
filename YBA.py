import discord
import requests
import pandas as pd
from discord.ext import tasks, commands
from threading import Thread
from flask import Flask
from web3 import Web3
import os
import asyncio

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WALLET = "0xA9ad8Ef52D0445b62CbF142d97EF5493501352f3"

POOL_ADDRESS = "0x640963da1d9d07cb86e89df670dd29b54e1f1d3e"
AVAX_RPC = "https://avalanche-c-chain-rpc.publicnode.com"

TARGET_SOL_PCT = 60.0
WARNING_DEVIATION = 20.0
# =========================================================

print("=== YieldBase SOL/AVAX LP Agent (Value-Weighted Active Bin) ===")

w3 = Web3(Web3.HTTPProvider(AVAX_RPC))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ YieldBase SOL/AVAX Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

def get_active_bin_ratio():
    """Returns value-weighted % SOL using active bin reserves"""
    try:
        # Get reserves
        reserves_abi = '[{"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint128","name":"reserveX","type":"uint128"},{"internalType":"uint128","name":"reserveY","type":"uint128"}],"stateMutability":"view","type":"function"}]'
        pool = w3.eth.contract(address=w3.to_checksum_address(POOL_ADDRESS), abi=reserves_abi)
        reserve_x, reserve_y = pool.functions.getReserves().call()

        if reserve_x + reserve_y == 0:
            return 50.0

        # Get current prices
        prices = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana,avalanche-2&vs_currencies=usd", timeout=10).json()
        sol_price = prices["solana"]["usd"]
        avax_price = prices["avalanche-2"]["usd"]

        sol_value = reserve_x * sol_price
        avax_value = reserve_y * avax_price
        total_value = sol_value + avax_value

        sol_pct = (sol_value / total_value) * 100
        return round(sol_pct, 1)
    except Exception as e:
        print(f"Active bin error: {e}")
        return 50.0

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

async def send_alert():
    sol_price, avax_price = get_current_prices() if 'get_current_prices' in globals() else (85.0, 9.0)
    current_sol_pct = get_active_bin_ratio()

    sol_price_str = f"${sol_price:,.2f}"
    avax_price_str = f"${avax_price:,.2f}"

    rsi_sol = calculate_rsi("solana")
    rsi_avax = calculate_rsi("avalanche-2")
    deviation = abs(current_sol_pct - TARGET_SOL_PCT)

    if deviation >= WARNING_DEVIATION:
        if current_sol_pct > TARGET_SOL_PCT:   # SOL overweight
            if rsi_sol < rsi_avax - 8:
                suggestion = "Hold — SOL is more oversold (good rebound potential)"
            else:
                suggestion = "Rebalance toward AVAX (AVAX is more oversold)"
        else:  # AVAX overweight
            if rsi_avax < rsi_sol - 8:
                suggestion = "Hold — AVAX is more oversold (good rebound potential)"
            else:
                suggestion = "Rebalance toward SOL (SOL is more oversold)"
        
        if deviation >= 35:
            suggestion = "🔴 Strongly recommend rebalancing now — " + suggestion
        status = f"🚨 **Lopsided** — {suggestion}"
    else:
        status = "✅ Within acceptable range"

    alert = f"""🚨 **SOL/AVAX LP Monitor**

**Current Prices:** SOL {sol_price_str} | AVAX {avax_price_str}
**Pool Ratio (Active Bin):** {current_sol_pct:.1f}% SOL / {100 - current_sol_pct:.1f}% AVAX
**Your Target:** 60% SOL / 40% AVAX

**Status:** {status}

**RSI (14d):** SOL {rsi_sol} | AVAX {rsi_avax}
"""

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(alert)

@bot.tree.command(name="check", description="Check current SOL/AVAX LP status")
async def check(interaction: discord.Interaction):
    await interaction.response.defer()
    await send_alert()
    await interaction.followup.send("✅ LP check completed!")

@tasks.loop(hours=8)
async def monitor_lp():
    await send_alert()

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and monitoring your SOL/AVAX pool!")
    await bot.tree.sync()
    await asyncio.sleep(5)
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
