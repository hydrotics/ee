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
ROLE_ID = int(os.getenv("ROLE_ID"))  # Role ID is now stored in the .env file
nlp = spacy.load("en_core_web_sm")

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    # Ensure structure exists
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

# Global data
TRIGGERS_DATA = load_triggers()
RESPONSES = TRIGGERS_DATA.get("responses", {})
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

    if len(message.content.split()) < 2:  # Requires at least two words
        return None

    matched_response = None
    highest_score = 0

    question_words_in_message = [token.text for token in doc if token.text in QUESTION_START]
    if not question_words_in_message:
        return None

    triggers_found = False
    complaint_keywords = {"complain", "annoyed", "tired", "sick", "waiting", "long", "give us"}
    required_triggers = {"update", "mobile", "support"}
    force_triggers = TRIGGERS_DATA.get("force", {})
    reporting_force_triggers = force_triggers.get("reporting", [])

    if any(trigger in message.content.lower() for trigger in reporting_force_triggers):
        print("⚡ Force trigger detected; responding with reporting response.")
        return "> __**Link to Levi's Projects Support Server**__ https://discord.gg/edQF7AhTf6"

    if any(word in message.content.lower() for word in complaint_keywords) and any(word in message.content.lower() for word in required_triggers):
        req_category = None
        if "update" in message.content.lower():
            req_category = "update"
        elif "mobile" in message.content.lower():
            req_category = "mobile"
        elif "support" in message.content.lower():
            req_category = "reporting"
        if req_category:
            print(f"⚡ Complaint and required trigger detected; forcing {req_category} response.")
            for resp, data in TRIGGERS_DATA.get("responses", {}).items():
                if data.get("category") == req_category:
                    return resp

    if "support" in message.content.lower():
        if "mobile" in message.content.lower():  # If mobile is also mentioned, handle as mobile
            return "> Mobile support will not be available until the update. Please be patient."
        else:  # Support-related response
            print("⚡ Responding with support server link.")
            return "> __**Link to Levi's Projects Support Server**__ https://discord.gg/edQF7AhTf6"

    intent, category = analyze_intent(message.content)

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

    if intent == "asking" and matched_response:
        print(f"✅ Responding with: {matched_response} (User is asking about {category})")
        return matched_response
    elif intent == "informing" and matched_response:
        return matched_response

    return None

def generate_variants(base_word):
    variations = {base_word}
    suffixes = ["s", "ing", "ed"]
    for suffix in suffixes:
        variations.add(base_word + suffix)
    return variations

# --- Commands ---
@bot.tree.command(name="autoresponder-channel", description="Sets the channel where the bot will listen for trigger messages.")
async def autoresponder_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if ROLE_ID not in [role.id for role in interaction.user.roles]:  # Check if user has the required role
        await interaction.response.send_message(
            "❌ You do not have the required role to use this command.", ephemeral=True
        )
        return

    global TRIGGERS_DATA
    if TRIGGERS_DATA.get("channel_id") == channel.id:
        await interaction.response.send_message("❌ This channel is already set as the autoresponder channel.", ephemeral=True)
    else:
        TRIGGERS_DATA["channel_id"] = channel.id
        save_triggers(TRIGGERS_DATA)
        await interaction.response.send_message(
            f"✅ The autoresponder channel has been set to {channel.mention}. The bot will now only respond in this channel.",
            ephemeral=True
        )

@bot.tree.command(name="autoresponder-create", description="Creates a new autoresponder with the specified category, triggers, and response.")
async def autoresponder_create(
    interaction: discord.Interaction,
    category: str,
    triggers: str,
    response: str
):
    if ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message(
            "❌ You do not have the required role to use this command.", ephemeral=True
        )
        return

    global TRIGGERS_DATA
    responses = TRIGGERS_DATA.get("responses", {})
    trigger_list = [trigger.strip().lower() for trigger in triggers.split(",")]
    new_response = {
        "triggers": trigger_list,
        "category": category,
        "response": response,
        "created_by_command": True
    }
    responses[category] = new_response
    TRIGGERS_DATA["responses"] = responses
    save_triggers(TRIGGERS_DATA)
    await interaction.response.send_message(
        f"✅ Successfully created the new autoresponder category '{category}' with response: '{response}'",
        ephemeral=True
    )

@bot.tree.command(name="autoresponder-delete", description="Deletes an existing autoresponder category.")
async def autoresponder_delete(interaction: discord.Interaction, category: str):
    if ROLE_ID not in [role.id for role in interaction.user.roles]:  # Check if user has the required role
        await interaction.response.send_message(
            "❌ You do not have the required role to use this command.", ephemeral=True
        )
        return

    global TRIGGERS_DATA
    if category in TRIGGERS_DATA.get("responses", {}):
        del TRIGGERS_DATA["responses"][category]
        save_triggers(TRIGGERS_DATA)
        await interaction.response.send_message(f"✅ The autoresponder category '{category}' has been deleted.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No autoresponder category named '{category}' found.", ephemeral=True)

@autoresponder_delete.autocomplete("category")
async def autoresponder_delete_autocomplete(interaction: discord.Interaction, current: str):
    """Shows only categories created by command that meet Discord's requirements."""
    responses = TRIGGERS_DATA.get("responses", {})
    valid_categories = [
        cat for cat, data in responses.items() 
        if data.get("created_by_command") is True and 1 <= len(cat) <= 100
    ]

    if not current:
        return [app_commands.Choice(name=cat, value=cat) for cat in valid_categories[:25]]

    filtered = [cat for cat in valid_categories if current.lower() in cat.lower()]
    return [app_commands.Choice(name=cat, value=cat) for cat in filtered[:25]]

@bot.tree.command(name="autoresponder-list", description="Lists all autoresponders created by command.")
async def autoresponder_list(interaction: discord.Interaction):
    """Lists all autoresponders created via command."""
    responses = TRIGGERS_DATA.get("responses", {})
    embed = discord.Embed(
        title="Autoresponder List",
        color=EMBED_COLOR_HEX
    )

    created_responses = {cat: data for cat, data in responses.items() if data.get("created_by_command") is True}

    if not created_responses:
        embed.add_field(name="No autoresponders found", value="There are no autoresponders created by command.", inline=False)
    else:
        for i, (category, data) in enumerate(created_responses.items(), start=1):
            triggers_list = data.get("triggers", [])
            triggers_str = ", ".join(triggers_list) if triggers_list else "None"
            response_text = data.get("response", "No response provided")
            embed.add_field(
                name=f"{i}. Category: {category}",
                value=f"Triggers: {triggers_str}\nResponse: {response_text}",
                inline=False
            )

    await interaction.response.send_message(embed=embed)

# --- Bot Run ---
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Levi's Projects"))
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Only respond in the designated autoresponder channel (if set)
    channel_id = TRIGGERS_DATA.get("channel_id")
    if channel_id and message.channel.id != channel_id:
        return

    response = get_response(message)
    if response:
        await message.channel.send(response)

bot.run(TOKEN)
