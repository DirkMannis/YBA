import discord
import requests
import pandas as pd
from discord.ext import tasks
from threading import Thread
from flask import Flask
import os

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DEBANK_KEY = os.getenv("DEBANK_KEY")
WALLET = "0xA9ad8Ef52D0445b62CbF142d97EF5493501352f3"

TARGET_SOL_PCT = 60.0
WARNING_DEVIATION = 20.0
# =========================================================

if not all([DISCORD_TOKEN, CHANNEL_ID, DEBANK_KEY]):
    raise ValueError("❌ Missing one or more environment variables! Check Render Environment tab.")

CHANNEL_ID = int(CHANNEL_ID)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "YieldBase SOL/AVAX Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def get_debank_position():
    urls = [
        f"https://pro-openapi.debank.com/v1/user/complex_protocol_list?id={WALLET}",
        f"https://pro-openapi.debank.com/v1/user/all_complex_protocol_list?id={WALLET}"
    ]
    
    headers = {"AccessKey": DEBANK_KEY}
    
    for url in urls:
        try:
            print(f"Trying DeBank URL: {url}")
            resp = requests.get(url, headers=headers, timeout=20).json()
            
            if isinstance(resp, list):
                for protocol in resp:
                    name = str(protocol.get("name", "")).lower()
                    if any(x in name for x in ["lfj", "traderjoe", "liquiditybook", "avax"]):
                        for item in protocol.get("portfolio_item_list", []):
                            tokens = item.get("supply_token_list", [])
                            if len(tokens) >= 2:
                                sol = next((t for t in tokens if t.get("symbol") in ["SOL", "wSOL"]), None)
                                avax = next((t for t in tokens if t.get("symbol") in ["AVAX", "WAVAX"]), None)
                                if sol and avax:
                                    print("✅ Successfully found SOL/AVAX LP position on DeBank!")
                                    return {
                                        "sol_amount": float(sol.get("amount", 0)),
                                        "avax_amount": float(avax.get("amount", 0)),
                                    }
        except Exception as e:
            print(f"DeBank API error: {e}")
    
    print("❌ Could not find LP position in any DeBank response")
    return None

def get_current_prices():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana,avalanche-2&vs_currencies=usd", timeout=10).json()
        return data["solana"]["usd"], data["avalanche-2"]["usd"]
    except:
        return 85.0, 9.0  # fallback prices

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

@tasks.loop(hours=8)
async def monitor_lp():
    position = get_debank_position()
    if not position:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("⚠️ Could not fetch LP position from DeBank. Check API key or pool visibility.")
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

        suggestion = "Consider rebalancing toward 60/40"
        if deviation >= 35:
            suggestion = "**Strongly recommend rebalancing now**"

        alert = f"""🚨 **SOL/AVAX LP Lopsided Alert!**

**Current:** {sol_pct}% SOL / {avax_pct}% AVAX   (Target: 60/40)
**Total Value:** ~${total:,.0f}

**RSI (14d):** SOL {rsi_sol} | AVAX {rsi_avax}
{suggestion}"""

        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(alert)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and monitoring your SOL/AVAX pool!")
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
