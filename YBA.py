import discord
import os
import asyncio
from threading import Thread
from flask import Flask

# ========================= CONFIG =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
# =========================================================

print("=== YieldBase LP Agent - Minimal Test Starting ===")
print(f"Discord Token Present: {bool(DISCORD_TOKEN)}")
print(f"Channel ID: {CHANNEL_ID}")

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ YieldBase Bot is running on Railway!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

@bot.event
async def on_ready():
    print(f"✅ SUCCESS: {bot.user} is ONLINE on Railway!")
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("✅ **YieldBase LP Agent is now online on Railway!** Minimal test successful.")
            print("Test message sent to Discord channel.")
    except Exception as e:
        print(f"Could not send test message: {e}")
    
    # Keep Flask alive
    Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
