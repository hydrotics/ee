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
def get_embed_color():
    """Get embed color from triggers.json"""
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("embed_color", 0xFFFFFF)
    except:
        return 0xFFFFFF

EMBED_COLOR_HEX = get_embed_color()

# --- Environment Detection ---
IS_RENDER = os.getenv("RENDER") is not None  # Render sets this env var automatically

# --- Keep-Alive Setup ---
app = Flask(__name__)

@app.route("/")
def home():
    return "I'm alive!"

@app.route("/health")
def health():
    return "OK", 200

def run_dev():
    """Run Flask development server (VS Code)"""
    app.run(host="0.0.0.0", port=8080)

def run_prod():
    """Run with Gunicorn (Render)"""
    # Gunicorn will handle running the app
    pass

def keep_alive():
    if IS_RENDER:
        # On Render, Gunicorn handles the Flask app separately
        # We don't need to start Flask in a thread
        print("Running on Render - Gunicorn will handle Flask")
    else:
        # Local development - use Flask dev server
        print("Running locally - starting Flask dev server")
        server = Thread(target=run_dev)
        server.daemon = True
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
    # Process the message without enforcing a minimum word count.
    doc = nlp(message.content.lower())

    # Refresh trigger data from file
    with open("triggers.json", "r", encoding="utf-8") as f:
        triggers_data = json.load(f)

    for autoresponder_name, data in triggers_data.get("responses", {}).items():
        triggers = set(data.get("triggers", []))
        # Default smart detection to True ("yes") if missing.
        smart_detection = data.get("smart_detection", True)

        if not smart_detection:
            # When smart detection is "no", reply if ANY trigger is found anywhere in the message.
            if any(trigger in message.content.lower().split() for trigger in triggers):
                return data.get("response", autoresponder_name)
        else:
            # When smart detection is "yes", require both a question word and a trigger match.
            question_words_in_message = any(token.text in QUESTION_START for token in doc)
            trigger_matches = sum(
                1 for token in doc if any(
                    difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8
                    for trigger in triggers)
            )
            if question_words_in_message and trigger_matches > 0:
                return data.get("response", autoresponder_name)
    return None

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Levi's Projects"))
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    print(f"Environment: {'Render (Production)' if IS_RENDER else 'Local (Development)'}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    refresh_triggers()

    # If allowed channels are defined, ensure the message is in one of them.
    channel_ids = TRIGGERS_DATA.get("channel_ids", [])
    if channel_ids and message.channel.id not in channel_ids:
        return

    response = get_response(message)
    if response:
        await message.channel.send(response)

# --- Extension Loading ---
async def main():
    async with bot:
        await bot.load_extension("commands.autoresponder_list")
        await bot.load_extension("commands.autoresponder_create")
        await bot.load_extension("commands.autoresponder_edit")
        await bot.load_extension("commands.autoresponder_delete")
        await bot.load_extension("commands.autoresponder_channel")
        task = asyncio.create_task(bot.start(TOKEN))
        await task

if __name__ == "__main__":
    asyncio.run(main())
