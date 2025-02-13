import discord
import json
import os
import spacy
import difflib
from discord.ext import commands
from dotenv import load_dotenv

from flask import Flask
from threading import Thread

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

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

nlp = spacy.load("en_core_web_sm")

# Load responses and other data from JSON
def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error loading triggers.json: {e}")
        return {}

data = load_triggers()
RESPONSES = data.get("responses", {})
CHANNEL_ID = data.get("channel_id", 1324435423602413664)
QUESTION_START = set(data.get("question_words", []))

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# AI function to detect category (update, mobile, etc.) based on triggers from JSON
def detect_category(message):
    doc = nlp(message.lower())
    detected_category = None
    highest_match_count = 0

    # Loop through each response's triggers in RESPONSES
    for response, data in RESPONSES.items():
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

# AI function to analyze if the message is asking a question or just a statement
def analyze_intent(message):
    doc = nlp(message.lower())
    is_question = any(token.text in QUESTION_START for token in doc)
    detected_category = detect_category(message)

    if is_question and detected_category:
        return "asking", detected_category
    elif detected_category:
        return "informing", detected_category
    return "neutral", None

# AI function to determine an appropriate response
def get_response(message):
    doc = nlp(message.lower())
    matched_response = None
    highest_score = 0

    print(f"🔎 Analyzing message: {message}")  # Debug log

    complaint_words = {"complain", "moan", "annoyed", "tired", "sick", "waiting", "long"}
    required_triggers = {"update", "mobile", "support"}

    if any(word in message.lower() for word in complaint_words) and any(word in message.lower() for word in required_triggers):
        req_category = None
        if "update" in message.lower():
            req_category = "update"
        elif "mobile" in message.lower():
            req_category = "mobile"
        elif "support" in message.lower():
            req_category = "reporting"  # Map 'support' to 'reporting'
        
        if req_category:
            print(f"⚡ Complaint and required trigger detected; forcing {req_category} response.")
            for resp, data in RESPONSES.items():
                if data.get("category") == req_category:
                    return resp
                    
    # Detect category (update, mobile, etc.)
    intent, category = analyze_intent(message)

    for response, data in RESPONSES.items():
        triggers = set(word.lower() for word in data["triggers"])
        response_category = data.get("category", None)

        if category and response_category and response_category != category:
            continue

        trigger_matches = sum(
            1 for token in doc if any(difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8 for trigger in triggers)
        )
        score = trigger_matches / len(triggers) if triggers else 0  # Normalize score

        print(f"⚖️ Score for '{response}' (Category: {response_category}): {score:.2f}")  # Debug log

        if score > highest_score:
            highest_score = score
            matched_response = response

    if intent == "asking":
        print(f"✅ Responding with: {matched_response} (User is asking about {category})")
        return matched_response
    elif intent == "informing":
        print(f"✅ Responding with: {matched_response} (User is informing about {category})")
    else:
        print("❌ No response matched.")
        return None

@bot.event
async def on_message(message):
    if message.channel.id == CHANNEL_ID and not message.author.bot:
        hacker_keywords = ["report", "exploiter", "hacker", "support", "support server", "help", "server", "cheater", "theres a hacker in my server"]
        if any(difflib.SequenceMatcher(None, word, keyword).ratio() > 0.8 for word in message.content.lower().split() for keyword in hacker_keywords):
            response = get_response(message.content)
            if response:
                await message.channel.send(response)
        else:
            response = get_response(message.content)
            if response:
                await message.channel.send(response)

    await bot.process_commands(message)

# Run the bot
bot.run(TOKEN)
