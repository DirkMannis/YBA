import discord
import requests
import pandas as pd
from discord.ext import tasks
from threading import Thread
from flask import Flask
import os
import asyncio
import time
import random

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_STR = os.getenv("CHANNEL_ID")
DEBANK_KEY = os.getenv("DEBANK_KEY")
WALLET = "0xA9ad8Ef52D0445b62CbF142d97EF5493501352f3"

TARGET_SOL_PCT = 60.0
WARNING_DEVIATION = 20.0
# =========================================================

print("=== YieldBase SOL/AVAX LP Agent Starting ===")
print(f"Tokens present: Discord={bool(DISCORD_TOKEN)}, DeBank={bool(DEBANK_KEY)}, Channel={bool(CHANNEL_ID_STR)}")

if not all([DISCORD_TOKEN, CHANNEL_ID_STR, DEBANK_KEY]):
    raise ValueError("Missing environment variables!")

CHANNEL_ID = int(CHANNEL_ID_STR)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ YieldBase Bot Running"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

async def safe_send(message):
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await asyncio.sleep(5)  # Heavy delay to avoid rate limits
            await channel.send(message)
    except discord.errors.HTTPException as e:
        if e.status == 429:
            print("Rate limited by Discord - will retry later")
        else:
            print(f"Discord send error: {e}")

def get_debank_position():
    # Same as before with retry
    urls = [
        f"https://pro-openapi.debank.com/v1/user/complex_protocol_list?id={WALLET}",
        f"https://pro-openapi.debank.com/v1/user/all_complex_protocol_list?id={WALLET}"
    ]
    headers = {"AccessKey": DEBANK_KEY}
    
    for url in urls:
        try:
            print(f"Fetching from DeBank...")
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code == 429:
                print("DeBank rate limited")
                time.sleep(10)
                continue
            data = resp.json()
            # ... parsing logic (same as previous) ...
            if isinstance(data, list):
                for protocol in data:
                    name = str(protocol.get("name", "")).lower()
                    if any(x in name for x in ["lfj", "traderjoe", "liquiditybook"]):
                        for item in protocol.get("portfolio_item_list", []):
                            tokens = item.get("supply_token_list", [])
                            sol = next((t for t in tokens if t.get("symbol") in ["SOL", "wSOL"]), None)
                            avax = next((t for t in tokens if t.get("symbol") in ["AVAX", "WAVAX"]), None)
                            if sol and avax:
                                print("✅ LP Position Found!")
                                return {
                                    "sol_amount": float(sol.get("amount", 0)),
                                    "avax_amount": float(avax.get("amount", 0))
                                }
        except Exception as e:
            print(f"DeBank error: {e}")
    return None

# Keep get_current_prices and calculate_rsi the same (with retry if needed)

@tasks.loop(hours=8)
async def monitor_lp():
    position = get_debank_position()
    if not position:
        await safe_send("⚠️ Could not fetch LP position from DeBank.")
        return
    # ... rest of calculation and alert (same as before) ...

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online!")
    await asyncio.sleep(15)   # Long delay after start
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
