# main.py
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

load_dotenv()

def get_embed_color():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("embed_color", 0xFFFFFF)
    except Exception:
        return 0xFFFFFF

EMBED_COLOR_HEX = get_embed_color()

IS_RENDER = os.getenv("RENDER") is not None

app = Flask(__name__)

@app.route("/")
def home():
    return "I'm alive!"

@app.route("/health")
def health():
    return "OK", 200

def run_dev():
    app.run(host="0.0.0.0", port=8080)

if not IS_RENDER:
    server = Thread(target=run_dev)
    server.daemon = True
    server.start()

TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv("ROLE_IDS", "").split(",") if role_id.strip()]
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

    for key, value in data.get("responses", {}).items():
        if "smart_detection" not in value:
            value["smart_detection"] = True

    return data

def save_triggers(triggers_data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(triggers_data, f, ensure_ascii=False, indent=4)

TRIGGERS_DATA = load_triggers()
QUESTION_START = set(TRIGGERS_DATA.get("question_words", []))

def refresh_triggers():
    global TRIGGERS_DATA, QUESTION_START, EMBED_COLOR_HEX
    TRIGGERS_DATA = load_triggers()
    QUESTION_START = set(TRIGGERS_DATA.get("question_words", []))
    EMBED_COLOR_HEX = get_embed_color()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_response(message):
    doc = nlp(message.content.lower())
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            triggers_data = json.load(f)
    except Exception:
        triggers_data = {}

    for autoresponder_name, data in triggers_data.get("responses", {}).items():
        triggers = set(data.get("triggers", []))
        smart_detection = data.get("smart_detection", True)

        if not smart_detection:
            if any(trigger in message.content.lower().split() for trigger in triggers):
                return data.get("response", autoresponder_name)
        else:
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
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"Logged in as {bot.user}")
    print(f"Environment: {'Render (Production)' if IS_RENDER else 'Local (Development)'}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    refresh_triggers()

    channel_ids = TRIGGERS_DATA.get("channel_ids", [])
    if channel_ids and message.channel.id not in channel_ids:
        return

    response = get_response(message)
    if response:
        await message.channel.send(response)

EXTENSIONS = [
    "commands.autoresponder_list",
    "commands.autoresponder_create",
    "commands.autoresponder_edit",
    "commands.autoresponder_delete",
    "commands.autoresponder_channel",
]

BOT_THREAD_STARTED = False

def start_bot_in_background():
    global BOT_THREAD_STARTED
    if BOT_THREAD_STARTED:
        return
    if not TOKEN:
        print("DISCORD_TOKEN not set; bot will not start.")
        return

    def runner():
        async def _boot():
            for ext in EXTENSIONS:
                try:
                    bot.load_extension(ext)
                except Exception as e:
                    print(f"Failed to load extension {ext}: {e}")
            try:
                await bot.start(TOKEN)
            except Exception as e:
                print(f"Bot failed to start: {e}")
        try:
            asyncio.run(_boot())
        except Exception as e:
            print(f"Bot thread exited with error: {e}")

    thread = Thread(target=runner)
    thread.daemon = False
    thread.start()
    BOT_THREAD_STARTED = True

start_bot_in_background()
