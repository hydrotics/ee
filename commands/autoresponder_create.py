import discord
import json
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
ROLE_ID = int(os.getenv("ROLE_ID"))

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_triggers(data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class AutoresponderCreate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-create", 
        description="Creates a new autoresponder with the specified category, triggers, and response."
    )
    async def autoresponder_create(
        self, interaction: discord.Interaction, category: str, triggers: str, response: str
    ):
        if ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.", ephemeral=True
            )
            return

        triggers_data = load_triggers()
        responses = triggers_data.get("responses", {})

        trigger_list = [trigger.strip().lower() for trigger in triggers.split(",")]
        new_response = {
            "triggers": trigger_list,
            "category": category,
            "response": response,
            "created_by_command": True
        }
        responses[category] = new_response
        triggers_data["responses"] = responses
        save_triggers(triggers_data)

        await interaction.response.send_message(
            f"✅ Successfully created the new autoresponder category '{category}' with response: '{response}'",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderCreate(bot))
