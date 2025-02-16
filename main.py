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

# --- Flask App Setup (WSGI callable for Gunicorn) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "I'm alive!"

# --- Environment and Bot Setup ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_ID = int(os.getenv("ROLE_ID"))
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
def detect_category(message):
    doc = nlp(message.lower())
    detected_category = None
    highest_match_count = 0
    for resp, data in TRIGGERS_DATA.get("responses", {}).items():
        triggers = data.get("triggers", [])
        if not triggers:
            continue
        match_count = sum(
            1 for token in doc if any(difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8 for trigger in triggers)
        )
        if match_count > highest_match_count:
            highest_match_count = match_count
            detected_category = data.get("category", None)
    return detected_category

def analyze_intent(message):
    doc = nlp(message.lower())
    is_question = any(token.text in QUESTION_START for token in doc) or message.endswith("?")
    detected_category = detect_category(message)
    if is_question and detected_category:
        return "asking", detected_category
    elif detected_category:
        return "informing", detected_category
    return "neutral", None

def get_response(message):
    doc = nlp(message.content.lower())
    if len(message.content.split()) < 2:
        return None

    question_words_in_message = [token.text for token in doc if token.text in QUESTION_START]
    if not question_words_in_message:
        return None

    complaint_keywords = {"complain", "annoyed", "tired", "sick", "waiting", "long", "give us"}
    required_triggers = {"update", "mobile", "support"}
    force_triggers = TRIGGERS_DATA.get("force", {})
    reporting_force_triggers = force_triggers.get("reporting", [])

    # Check force triggers first
    if any(trigger in message.content.lower() for trigger in reporting_force_triggers):
        return "> __**Link to Levi's Projects Support Server**__ https://discord.gg/edQF7AhTf6"

    if (any(word in message.content.lower() for word in complaint_keywords) and 
        any(word in message.content.lower() for word in required_triggers)):
        for resp, data in TRIGGERS_DATA.get("responses", {}).items():
            if data.get("category") in required_triggers:
                return resp

    intent, category = analyze_intent(message.content)
    matched_response = None
    highest_score = 0

    for cat, data in TRIGGERS_DATA.get("responses", {}).items():
        response_text = data.get("response", cat)
        triggers = set(word.lower() for word in data.get("triggers", []))
        trigger_matches = sum(
            1 for token in doc if any(difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8 for trigger in triggers)
        )
        score = trigger_matches / len(triggers) if triggers else 0
        if score > highest_score:
            highest_score = score
            matched_response = response_text

    if intent in ["asking", "informing"] and matched_response:
        return matched_response
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
    channel_id = TRIGGERS_DATA.get("channel_id")
    if channel_id and message.channel.id != channel_id:
        return
    response = get_response(message)
    if response:
        await message.channel.send(response)

# --- Extension Loading ---
async def main():
    async with bot:
        await bot.load_extension("commands.autoresponder_list")
        await bot.load_extension("commands.autoresponder_create")
        await bot.load_extension("commands.autoresponder_delete")
        await bot.load_extension("commands.autoresponder_channel")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
