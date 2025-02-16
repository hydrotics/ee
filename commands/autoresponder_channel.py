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

class AutoresponderChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-channel", 
        description="Sets the channel where the bot will listen for trigger messages."
    )
    async def autoresponder_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.", ephemeral=True
            )
            return

        triggers_data = load_triggers()
        if triggers_data.get("channel_id") == channel.id:
            await interaction.response.send_message(
                "❌ This channel is already set as the autoresponder channel.", ephemeral=True
            )
        else:
            triggers_data["channel_id"] = channel.id
            save_triggers(triggers_data)
            await interaction.response.send_message(
                f"✅ The autoresponder channel has been set to {channel.mention}. The bot will now only respond in this channel.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderChannel(bot))
