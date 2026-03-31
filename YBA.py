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
print(f"Discord Token: {'✅ Present' if DISCORD_TOKEN else '❌ Missing'}")
print(f"DeBank Key: {'✅ Present' if DEBANK_KEY else '❌ Missing'}")
print(f"Channel ID: {CHANNEL_ID_STR}")

if not all([DISCORD_TOKEN, CHANNEL_ID_STR, DEBANK_KEY]):
    raise ValueError("❌ Missing environment variables in Render!")

CHANNEL_ID = int(CHANNEL_ID_STR)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "YieldBase SOL/AVAX Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def make_request_with_retry(url, headers=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 429 or "cloudflare" in r.text.lower():
                wait = (2 ** attempt) + random.uniform(1, 3)
                print(f"Rate limited. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            return r.json()
        except Exception as e:
            print(f"Request error (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return None

def get_debank_position():
    urls = [
        f"https://pro-openapi.debank.com/v1/user/complex_protocol_list?id={WALLET}",
        f"https://pro-openapi.debank.com/v1/user/all_complex_protocol_list?id={WALLET}"
    ]
    headers = {"AccessKey": DEBANK_KEY}
    
    for url in urls:
        try:
            print(f"Trying DeBank: {url}")
            data = make_request_with_retry(url, headers=headers)
            if not data:
                continue
                
            if isinstance(data, list):
                for protocol in data:
                    name = str(protocol.get("name", "")).lower()
                    if any(x in name for x in ["lfj", "traderjoe", "liquiditybook"]):
                        for item in protocol.get("portfolio_item_list", []):
                            tokens = item.get("supply_token_list", [])
                            if len(tokens) >= 2:
                                sol = next((t for t in tokens if t.get("symbol") in ["SOL", "wSOL"]), None)
                                avax = next((t for t in tokens if t.get("symbol") in ["AVAX", "WAVAX"]), None)
                                if sol and avax:
                                    print("✅ Found SOL/AVAX LP position!")
                                    return {
                                        "sol_amount": float(sol.get("amount", 0)),
                                        "avax_amount": float(avax.get("amount", 0))
                                    }
        except Exception as e:
            print(f"DeBank error: {e}")
    
    print("❌ Could not fetch LP position from DeBank")
    return None

def get_current_prices():
    data = make_request_with_retry("https://api.coingecko.com/api/v3/simple/price?ids=solana,avalanche-2&vs_currencies=usd")
    if data:
        return data.get("solana", {}).get("usd", 85.0), data.get("avalanche-2", {}).get("usd", 9.0)
    return 85.0, 9.0

def calculate_rsi(coin_id: str, days=14):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
        data = make_request_with_retry(url)
        if data and "prices" in data:
            df = pd.DataFrame(data["prices"], columns=["ts", "price"])
            delta = df["price"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return round(rsi.iloc[-1], 1)
    except:
        pass
    return 50.0

@tasks.loop(hours=8)
async def monitor_lp():
    position = get_debank_position()
    if not position:
        await safe_send("⚠️ Could not fetch LP position from DeBank right now.")
        return

    sol_price, avax_price = get_current_prices()
    sol_value = position["sol_amount"] * sol_price
    avax_value = position["avax_amount"] * avax_price
    total = sol_value + avax_value
    if total == 0:
        return

    sol_pct = round((sol_value / total) * 100, 1)
    avax_pct = round(100 - sol_pct, 1)
    deviation = abs(sol_pct - TARGET_SOL_PCT)

    if deviation >= WARNING_DEVIATION:
        rsi_sol = calculate_rsi("solana")
        rsi_avax = calculate_rsi("avalanche-2")
        suggestion = "**Strongly recommend rebalancing now**" if deviation >= 35 else "Consider rebalancing toward 60/40"

        alert = f"""🚨 **SOL/AVAX LP Lopsided Alert!**

**Current:** {sol_pct}% SOL / {avax_pct}% AVAX   (Target: 60/40)
**Total Value:** ~${total:,.0f}
**RSI (14d):** SOL {rsi_sol} | AVAX {rsi_avax}
{suggestion}"""

        await safe_send(alert)

async def safe_send(message):
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await asyncio.sleep(3)
            await channel.send(message)
    except Exception as e:
        print(f"Send error: {e}")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and monitoring your SOL/AVAX pool!")
    await asyncio.sleep(10)   # Extra delay after rate limits
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
