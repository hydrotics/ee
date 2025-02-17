import discord
import json
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Load multiple role IDs from .env (split them by commas)
ROLE_IDS = [int(role_id) for role_id in os.getenv("ROLE_IDS", "").split(",")]

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_triggers(data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class AutoresponderDelete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-delete", 
        description="Deletes an existing autoresponder category."
    )
    async def autoresponder_delete(self, interaction: discord.Interaction, category: str):
        # Check if the user has one of the allowed roles
        if not any(role.id in ROLE_IDS for role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.", ephemeral=True
            )
            return

        triggers_data = load_triggers()
        if category in triggers_data.get("responses", {}):
            del triggers_data["responses"][category]
            save_triggers(triggers_data)
            await interaction.response.send_message(
                f"✅ The autoresponder category '{category}' has been deleted.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ No autoresponder category named '{category}' found.", ephemeral=True
            )

    @autoresponder_delete.autocomplete("category")
    async def autoresponder_delete_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        triggers_data = load_triggers()
        responses = triggers_data.get("responses", {})
        valid_categories = [
            cat for cat, data in responses.items()
            if data.get("created_by_command") is True and 1 <= len(cat) <= 100
        ]
        filtered = [cat for cat in valid_categories if current.lower() in cat.lower()]
        return [app_commands.Choice(name=cat, value=cat) for cat in filtered[:25]]

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderDelete(bot))
