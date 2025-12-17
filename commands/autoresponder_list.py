import discord
from discord import app_commands
from discord.ext import commands
from main import load_triggers  # Import only load_triggers

class AutoresponderList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-list", 
        description="Lists all autoresponders created by command."
    )
    async def autoresponder_list(self, interaction: discord.Interaction):
        triggers_data = load_triggers()
        embed_color = triggers_data.get("embed_color", 0xFFFFFF)
        responses = triggers_data.get("responses", {})

        embed = discord.Embed(title="Autoresponder List", color=embed_color)

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
