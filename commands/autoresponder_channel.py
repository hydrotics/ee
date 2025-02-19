import discord
import json
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Load allowed role IDs from .env (split by commas)
ROLE_IDS = [int(role_id) for role_id in os.getenv("ROLE_IDS", "").split(",") if role_id.strip()]

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_triggers(data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class AutoresponderChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-config", 
        description="Sets two channels where the bot will listen for trigger messages."
    )
    async def autoresponder_config(
        self, 
        interaction: discord.Interaction, 
        channel1: discord.TextChannel, 
        channel2: discord.TextChannel
    ):
        # Check if the user has one of the allowed roles
        if not any(role.id in ROLE_IDS for role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.", ephemeral=True
            )
            return

        triggers_data = load_triggers()

        # Ensure "channel_ids" exists as a list
        triggers_data["channel_ids"] = [channel1.id, channel2.id]

        save_triggers(triggers_data)

        await interaction.response.send_message(
            f"✅ Autoresponder channels have been set to {channel1.mention} and {channel2.mention}.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderChannel(bot))
