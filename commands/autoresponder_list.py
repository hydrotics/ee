import discord
from discord import app_commands
from discord.ext import commands
from main import EMBED_COLOR_HEX, load_triggers  # Import load_triggers from main

class AutoresponderList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-list", 
        description="Lists all autoresponders created by command."
    )
    async def autoresponder_list(self, interaction: discord.Interaction):
        # Reload triggers from disk
        triggers_data = load_triggers()
        responses = triggers_data.get("responses", {})

        embed = discord.Embed(title="Autoresponder List", color=EMBED_COLOR_HEX)

        # Filter to only include those created via command
        created_responses = {
            cat: data for cat, data in responses.items()
            if data.get("created_by_command") is True
        }

        if not created_responses:
            embed.add_field(
                name="No autoresponders found", 
                value="There are no autoresponders created by command.", 
                inline=False
            )
        else:
            for category, data in created_responses.items():
                triggers_list = data.get("triggers", [])
                triggers_str = ", ".join(triggers_list) if triggers_list else "None"
                response_text = data.get("response", "No response provided")
                embed.add_field(
                    name=f"Category: {category}",
                    value=f"Triggers: {triggers_str}\nResponse: {response_text}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderList(bot))
