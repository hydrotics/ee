import discord
import json
import os
import spacy
import difflib
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import asyncio

# --- Customization Options ---
EMBED_COLOR_HEX = 0xFFFFFF

# --- Keep-Alive Setup ---
app = Flask(__name__)

@app.route("/")
def home():
    return "I'm alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    server = Thread(target=run)
    server.start()

keep_alive()

# --- Environment and Bot Setup ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv("ROLE_IDS", "").split(",")]
nlp = spacy.load("en_core_web_sm")

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    if "responses" not in data:
        data["responses"] = {}
    if "question_words" not in data:
        data["question_words"] = []
    if "force" not in data:
        data["force"] = {}

    # Ensure all autoresponders default to smart detection enabled (yes)
    for key, value in data.get("responses", {}).items():
        if "smart_detection" not in value:
            value["smart_detection"] = True  # Default to "yes"

    return data

def save_triggers(triggers_data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(triggers_data, f, ensure_ascii=False, indent=4)

# Global triggers data and question words (initially loaded)
TRIGGERS_DATA = load_triggers()
QUESTION_START = set(TRIGGERS_DATA.get("question_words", []))

def refresh_triggers():
    """Reload triggers data from file and update globals."""
    global TRIGGERS_DATA, QUESTION_START
    TRIGGERS_DATA = load_triggers()
    QUESTION_START = set(TRIGGERS_DATA.get("question_words", []))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Utility Functions ---
def get_response(message):
    doc = nlp(message.content.lower())
    if len(message.content.split()) < 2:
        return None

    # Refresh trigger data from file
    with open("triggers.json", "r", encoding="utf-8") as f:
        triggers_data = json.load(f)

    for autoresponder_name, data in triggers_data.get("responses", {}).items():
        triggers = set(data.get("triggers", []))

        # Default smart detection to "yes" if missing
        smart_detection = data.get("smart_detection", True)

        # If smart detection is OFF ("no"), respond if ANY trigger appears anywhere in the message
        if not smart_detection:
            if any(trigger in message.content.lower().split() for trigger in triggers):
                return data.get("response", autoresponder_name)

        # If smart detection is ON ("yes"), require context (question words or structured phrase)
        else:
            question_words_in_message = any(token.text in QUESTION_START for token in doc)
            trigger_matches = sum(
                1 for token in doc if any(difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8 for trigger in triggers)
            )
            if question_words_in_message and trigger_matches > 0:
                return data.get("response", autoresponder_name)

    return None

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Levi's Projects"))
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Refresh the triggers data so any changes from commands are applied
    refresh_triggers()

    # Get the list of allowed channels
    channel_ids = TRIGGERS_DATA.get("channel_ids", [])

    # Check if message is in one of the allowed channels
    if not channel_ids or message.channel.id not in channel_ids:
        return

    response = get_response(message)
    if response:
        await message.channel.send(response)

# --- Extension Loading ---
async def main():
    async with bot:
        await bot.load_extension("commands.autoresponder_list")
        await bot.load_extension("commands.autoresponder_create")
        await bot.load_extension("commands.autoresponder_edit")  # Ensure edit command is loaded
        await bot.load_extension("commands.autoresponder_delete")
        await bot.load_extension("commands.autoresponder_channel")
        # Start the bot
        task = asyncio.create_task(bot.start(TOKEN))

        await task

if __name__ == "__main__":
    asyncio.run(main())
