import discord
import os
import asyncio
from threading import Thread
from flask import Flask

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
# =========================================================

print("=== Starting minimal bot for testing ===")

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

@bot.event
async def on_ready():
    print(f"✅ SUCCESS: {bot.user} is online!")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("✅ Bot is now online on Render after cooldown.")
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
