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
    os.system("gunicorn -w 1 -b 0.0.0.0:8080 main:app")  # Run Gunicorn server

def keep_alive():
    server = Thread(target=run)
    server.start()

keep_alive()

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1324435423602413664  # Your channel ID

# Load NLP model
nlp = spacy.load("en_core_web_sm")

# Load responses from JSON
def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as file:
            return json.load(file)["responses"]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Error loading triggers.json: {e}")
        return {}

RESPONSES = load_triggers()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Define question words
QUESTION_START = {"when", "how", "what", "where", "will", "can", "does", "is", "should", "has", "I need"}

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

    # --- NEW BLOCK: Complaint + Required Trigger Check ---
    # Define sets for complaint words and required trigger words.
    complaint_words = {"complain", "moan", "annoyed", "tired", "sick", "waiting", "long"}
    required_triggers = {"update", "mobile", "support"}
    
    # Check if the message contains any complaint word and any required trigger.
    if any(word in message.lower() for word in complaint_words) and any(word in message.lower() for word in required_triggers):
        # Determine which required trigger word is present.
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
    # --- END NEW BLOCK ---

    # Detect category (update, mobile, etc.)
    intent, category = analyze_intent(message)

    for response, data in RESPONSES.items():
        triggers = set(word.lower() for word in data["triggers"])
        response_category = data.get("category", None)  # Ensure JSON has "category"

        # Only consider responses that match the detected category
        if category and response_category and response_category != category:
            continue

        # Score relevance based on fuzzy matching
        trigger_matches = sum(
            1 for token in doc if any(difflib.SequenceMatcher(None, token.text, trigger).ratio() > 0.8 for trigger in triggers)
        )
        score = trigger_matches / len(triggers) if triggers else 0  # Normalize score

        print(f"⚖️ Score for '{response}' (Category: {response_category}): {score:.2f}")  # Debug log

        if score > highest_score:
            highest_score = score
            matched_response = response

    # Respond based on detected intent
    if intent == "asking":
        print(f"✅ Responding with: {matched_response} (User is asking about {category})")
        return matched_response
    elif intent == "informing":
        print(f"✅ Responding with: {matched_response} (User is informing about {category})")
    else:
        print("❌ No response matched.")
        return None

# Event when a message is received
@bot.event
async def on_message(message):
    if message.channel.id == CHANNEL_ID and not message.author.bot:
        # Check for hacker-related phrases (preserved functionality)
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
