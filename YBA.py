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
WALLET = "0xA9ad8Ef52D0445b62CbF142d97EF5493501352f3"   # ← Your wallet added here

TARGET_SOL_PCT = 60.0
WARNING_DEVIATION = 20.0
# =========================================================

if not DISCORD_TOKEN or not CHANNEL_ID or not DEBANK_KEY:
    raise ValueError("❌ Missing environment variables! Check Render Environment tab.")

CHANNEL_ID = int(CHANNEL_ID)

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "YieldBase SOL/AVAX Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ... (rest of your functions: get_debank_position, get_current_prices, calculate_rsi, monitor_lp) ...

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and monitoring your SOL/AVAX pool!")
    monitor_lp.start()
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
