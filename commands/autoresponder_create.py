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
            data = json.load(f)
    except Exception:
        data = {}
    
    # Ensure embed_color exists
    if "embed_color" not in data:
        data["embed_color"] = 0xFFFFFF
    
    return data

def save_triggers(data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class CreateAutoresponderModal(discord.ui.Modal, title="Create New Autoresponder"):
    def __init__(self):
        super().__init__()

        self.category = discord.ui.TextInput(
            label="Category Name",
            placeholder="e.g., update, mobile, reporting",
            required=True,
            max_length=100
        )
        
        self.triggers = discord.ui.TextInput(
            label="Triggers (comma-separated)",
            placeholder="e.g., update, revamp, release",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.response = discord.ui.TextInput(
            label="Response Message",
            placeholder="The message to send when triggered",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000
        )
        
        self.smart_detection = discord.ui.TextInput(
            label="Smart Detection (yes/no)",
            placeholder="yes = requires question word, no = any trigger",
            required=True,
            default="yes",
            max_length=3
        )

        self.add_item(self.category)
        self.add_item(self.triggers)
        self.add_item(self.response)
        self.add_item(self.smart_detection)

    async def on_submit(self, interaction: discord.Interaction):
        triggers_data = load_triggers()
        responses = triggers_data.get("responses", {})

        # Validate smart detection input
        smart_detection_value = self.smart_detection.value.strip().lower()
        if smart_detection_value not in ["yes", "no"]:
            await interaction.response.send_message(
                "❌ Invalid value for Smart Detection. Use `yes` or `no`.",
                ephemeral=True
            )
            return

        # Check if category already exists
        category_name = self.category.value.strip()
        if category_name in responses:
            await interaction.response.send_message(
                f"❌ An autoresponder with category '{category_name}' already exists. Use `/autoresponder-edit` to modify it.",
                ephemeral=True
            )
            return

        # Parse triggers
        trigger_list = [trigger.strip().lower() for trigger in self.triggers.value.split(",") if trigger.strip()]
        
        if not trigger_list:
            await interaction.response.send_message(
                "❌ You must provide at least one trigger.",
                ephemeral=True
            )
            return

        # Create new autoresponder
        new_response = {
            "triggers": trigger_list,
            "category": category_name,
            "response": self.response.value,
            "smart_detection": (smart_detection_value == "yes"),
            "created_by_command": True
        }
        
        responses[category_name] = new_response
        triggers_data["responses"] = responses
        save_triggers(triggers_data)

        # Load embed color from triggers data
        embed_color = triggers_data.get("embed_color", 0xFFFFFF)
        
        # Build confirmation embed
        smart_mode = "Smart Detection" if smart_detection_value == "yes" else "Fixed Detection"
        
        embed = discord.Embed(
            title="✅ Autoresponder Created Successfully",
            color=embed_color,
            description=f"A new autoresponder has been created with the following configuration:"
        )
        
        embed.add_field(
            name="📝 Name",
            value=f"`{category_name}`",
            inline=False
        )
        
        embed.add_field(
            name="🔍 Triggers",
            value=f"`{', '.join(trigger_list)}`",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Mode",
            value=smart_mode,
            inline=True
        )
        
        embed.add_field(
            name="💬 Response",
            value=self.response.value if len(self.response.value) <= 1024 else self.response.value[:1021] + "...",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

class AutoresponderCreate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="autoresponder-create", 
        description="Opens a form to create a new autoresponder with category, triggers, and response."
    )
    async def autoresponder_create(self, interaction: discord.Interaction):
        # Check if the user has one of the allowed roles
        if not any(role.id in ROLE_IDS for role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ You do not have the required role to use this command.", 
                ephemeral=True
            )
            return

        # Open the modal
        await interaction.response.send_modal(CreateAutoresponderModal())

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderCreate(bot))
