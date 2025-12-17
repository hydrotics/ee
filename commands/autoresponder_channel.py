import discord
import json
import os
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

ROLE_IDS = [int(role_id) for role_id in os.getenv("ROLE_IDS", "").split(",") if role_id.strip()]

def load_triggers():
    try:
        with open("triggers.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    if "embed_color" not in data:
        data["embed_color"] = 0xFFFFFF
    if "channel_ids" not in data:
        data["channel_ids"] = []
    return data

def save_triggers(data):
    with open("triggers.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

class EchoMessageModal(discord.ui.Modal, title="Echo Message"):
    def __init__(self, channel_id: int, guild: discord.Guild):
        super().__init__()
        self.channel_id = channel_id
        self.guild = guild
        self.message_content = discord.ui.TextInput(label="Message Content", style=discord.TextStyle.paragraph, placeholder="Enter the message to send...", required=True, max_length=2000)
        self.add_item(self.message_content)

    async def on_submit(self, interaction: discord.Interaction):
        channel = self.guild.get_channel(self.channel_id) or interaction.client.get_channel(self.channel_id)
        if channel is None:
            await interaction.response.send_message("❌ Could not resolve the channel.", ephemeral=True)
            return
        try:
            await channel.send(self.message_content.value)
            await interaction.response.send_message(f"✅ Message sent to {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send message: {e}", ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, guild: discord.Guild, for_echo: bool = False):
        super().__init__(timeout=180)
        self.guild = guild
        self.for_echo = for_echo
        self.selected_channel = None

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Select a channel", min_values=1, max_values=1, channel_types=[discord.ChannelType.text])
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel_obj = select.values[0]
        if isinstance(channel_obj, str):
            ch_id = int(channel_obj)
            channel_obj = self.guild.get_channel(ch_id) or interaction.client.get_channel(ch_id)
        if channel_obj is None:
            await interaction.response.send_message("❌ Selected channel could not be resolved.", ephemeral=True)
            self.stop()
            return
        self.selected_channel = channel_obj
        if self.for_echo:
            await interaction.response.send_modal(EchoMessageModal(channel_obj.id, self.guild))
        else:
            await interaction.response.send_message(f"✅ Selected: {channel_obj.mention}", ephemeral=True)
        self.stop()

class ColorModal(discord.ui.Modal, title="Set Embed Color"):
    def __init__(self):
        super().__init__()
        self.color_value = None
        self.color_input = discord.ui.TextInput(label="Hex Color Code", placeholder="e.g., FFFFFF or #FFFFFF", required=True, max_length=7)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        color_str = self.color_input.value.strip().replace("#", "")
        try:
            self.color_value = int(color_str, 16)
            triggers = load_triggers()
            triggers["embed_color"] = self.color_value
            save_triggers(triggers)
            await interaction.response.send_message(f"✅ Color set to #{self.color_value:06X}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid hex color code.", ephemeral=True)

class ConfigView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.channel1 = None
        self.channel2 = None

    @discord.ui.select(placeholder="Choose a configuration option...", options=[
        discord.SelectOption(label="Set Channel 1", description="Select the first autoresponse channel", value="channel1"),
        discord.SelectOption(label="Set Channel 2", description="Select the second autoresponse channel", value="channel2"),
        discord.SelectOption(label="Set Embed Color", description="Modify the bot's default embed colour", value="color"),
        discord.SelectOption(label="Send Echo Message", description="Echo a message to a channel as the bot", value="echo")
    ])
    async def config_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        triggers = load_triggers()
        option = select.values[0]
        if option == "channel1":
            view = ChannelSelectView(interaction.guild)
            await interaction.response.send_message("Select Channel 1:", view=view, ephemeral=True)
            await view.wait()
            if view.selected_channel:
                self.channel1 = view.selected_channel
        elif option == "channel2":
            view = ChannelSelectView(interaction.guild)
            await interaction.response.send_message("Select Channel 2:", view=view, ephemeral=True)
            await view.wait()
            if view.selected_channel:
                self.channel2 = view.selected_channel
        elif option == "color":
            modal = ColorModal()
            await interaction.response.send_modal(modal)
            if getattr(modal, 'color_value', None) is not None:
                triggers = load_triggers()
                triggers['embed_color'] = modal.color_value
                save_triggers(triggers)
        elif option == "echo":
            view = ChannelSelectView(interaction.guild, for_echo=True)
            await interaction.response.send_message("Select a channel to send the echo message:", view=view, ephemeral=True)

    @discord.ui.button(label="Save", style=discord.ButtonStyle.success, emoji="💾")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        triggers = load_triggers()
        changes = False
        channel_ids = triggers.get("channel_ids", [None, None])
        while len(channel_ids) < 2: channel_ids.append(None)
        if self.channel1: channel_ids[0] = self.channel1.id; changes = True
        if self.channel2: channel_ids[1] = self.channel2.id; changes = True
        triggers["channel_ids"] = [cid for cid in channel_ids if cid]
        if changes:
            save_triggers(triggers)
        embed_color = triggers.get("embed_color", 0xFFFFFF)
        embed = discord.Embed(title="✅ Configuration Saved" if changes else "⚠️ No changes detected", description="Your configuration has been updated." if changes else "No configuration changes.", color=embed_color)
        mentions = [interaction.guild.get_channel(cid).mention for cid in triggers.get("channel_ids", []) if interaction.guild.get_channel(cid)]
        if mentions: embed.add_field(name="Active Channels", value=", ".join(mentions), inline=False)
        embed.add_field(name="Embed Color", value=f"#{embed_color:06X}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Configuration cancelled.", embed=None, view=None)

class AutoresponderChannel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="autoresponder-config", description="Configure autoresponder settings.")
    async def autoresponder_config(self, interaction: discord.Interaction):
        if not any(role.id in ROLE_IDS for role in interaction.user.roles):
            await interaction.response.send_message("❌ You do not have the required role.", ephemeral=True)
            return
        triggers = load_triggers()
        embed_color = triggers.get("embed_color", 0xFFFFFF)
        embed = discord.Embed(title="Autoresponder settings", description="Use the dropdown to configure settings.", color=embed_color)
        chans = [interaction.guild.get_channel(cid).mention for cid in triggers.get("channel_ids", []) if interaction.guild.get_channel(cid)]
        embed.add_field(name="Current autoresponse Channels", value=", ".join(chans) if chans else "Not configured", inline=False)
        embed.add_field(name="Default embed colour", value=f"#{embed_color:06X}", inline=False)
        await interaction.response.send_message(embed=embed, view=ConfigView(interaction), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoresponderChannel(bot))
