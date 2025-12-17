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

class EditAutoresponderModal(discord.ui.Modal, title="Edit Autoresponder"):
    def __init__(self, bot, category: str, response: str, triggers: list, smart_detection: bool):
        super().__init__()
        self.bot = bot
        self.category = category

        # Pre-filled modal fields.
        # "yes" means the autoresponder requires both a question word plus a trigger.
        # "no" means it will reply on any trigger (all context discarded).
        self.response = discord.ui.TextInput(
            label="Response",
            style=discord.TextStyle.paragraph,
            required=True,
            default=response
        )
        self.triggers = discord.ui.TextInput(
            label="Triggers (comma-separated)",
            required=True,
            default=", ".join(triggers)
        )
        self.smart_detection = discord.ui.TextInput(
            label="Smart Detection (yes/no)",
            required=True,
            max_length=3,
            default="yes" if smart_detection else "no"
        )

        self.add_item(self.response)
        self.add_item(self.triggers)
        self.add_item(self.smart_detection)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_triggers()

        if self.category not in data.get("responses", {}):
            await interaction.response.send_message(
                f"Autoresponder `{self.category}` not found.",
                ephemeral=True
            )
            return

        smart_detection_value = self.smart_detection.value.strip().lower()
        if smart_detection_value not in ["yes", "no"]:
            await interaction.response.send_message(
                "Invalid value for Smart Detection. Use `yes` or `no`.",
                ephemeral=True
            )
            return

        # Update autoresponder details.
        data["responses"][self.category]["response"] = self.response.value
        data["responses"][self.category]["triggers"] = [
            trigger.strip().lower() for trigger in self.triggers.value.split(",")
        ]
        data["responses"][self.category]["smart_detection"] = (smart_detection_value == "yes")
        save_triggers(data)

        await interaction.response.send_message(
            f"Autoresponder `{self.category}` updated successfully!",
            ephemeral=True
        )

class AutoresponderEdit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="autoresponder-edit", description="Edit an existing autoresponder category.")
    @app_commands.describe(category="Select the name of the autoresponder you want to edit")
    async def autoresponder_edit(self, interaction: discord.Interaction, category: str):
        # Check if the user has one of the allowed roles
        if not any(role.id in ROLE_IDS for role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.",
                ephemeral=True
            )
            return
        
        data = load_triggers()
        if category not in data.get("responses", {}):
            await interaction.response.send_message(
                f"No autoresponder category found with name `{category}`.",
                ephemeral=True
            )
            return

        # Get existing autoresponder data.
        autoresponder = data["responses"][category]
        response = autoresponder.get("response", "")
        triggers = autoresponder.get("triggers", [])
        smart_detection = autoresponder.get("smart_detection", True)

        # Open modal with pre-filled values.
        await interaction.response.send_modal(
            EditAutoresponderModal(self.bot, category, response, triggers, smart_detection)
        )

    @autoresponder_edit.autocomplete("category")
    async def autoresponder_edit_autocomplete(self, interaction: discord.Interaction, current: str):
        data = load_triggers()
        responses = data.get("responses", {})
        # Use the same filtering as in your delete command:
        valid_categories = [
            cat for cat, info in responses.items()
            if info.get("created_by_command") is True and 1 <= len(cat) <= 100
        ]
        filtered = [cat for cat in valid_categories if current.lower() in cat.lower()]
        return [app_commands.Choice(name=cat, value=cat) for cat in filtered[:25]]

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderEdit(bot))
