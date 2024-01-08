import discord
from discord.ext import commands
from discord import Interaction, app_commands, ui
import requests
import numpy as np
import io
import cv2
import os

def extract_photos(input_image, aspect_ratio=(5.5, 8.5), min_percentage=0.5):
    gray = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, threshold = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    extracted_photos = []
    total_pixels = input_image.shape[1] * input_image.shape[0]
    min_size = np.sqrt(min_percentage / 100.0 * total_pixels)

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        ratio = float(w) / h

        if (aspect_ratio[0] / aspect_ratio[1] * 0.8 <= ratio <= aspect_ratio[0] / aspect_ratio[1] * 1.2 
            and w >= min_size and h >= min_size):
            photo = input_image[y:y+h, x:x+w]
            extracted_photos.append(photo)

    return extracted_photos

## CLIENT ##
client = commands.Bot(command_prefix=".", intents = discord.Intents.all(), activity=discord.Activity(type=discord.ActivityType.listening, name="Ditto"))
GIVEAWAY_MESSAGE_ID = 1194025455641174079 

@client.event
async def on_ready():
  GUILDS_ID = 1191857034254102528
  client.tree.copy_global_to(guild=discord.Object(id=GUILDS_ID))
  await client.tree.sync(guild=discord.Object(id=GUILDS_ID))
  channel = client.get_channel(1191860454495109360)
  message = await channel.fetch_message(GIVEAWAY_MESSAGE_ID)
  view = GiveawayView(message)
  await message.edit(view=view)

@client.event
async def on_member_join(member):
    welcome_channel_id = 1191870848785715300
    channel = client.get_channel(welcome_channel_id)

    embed = discord.Embed(
        title=f"Welcome to PCollect Place!",
        description=f"**We hope you enjoy your stay, {member.name}!**\n\nInvite others using this link: https://discord.gg/vJQGrrc8r5",
        color=int("FF2E98", 16)
    )
    embed.set_thumbnail(url=member.avatar)
    await channel.send(embed=embed)

@client.tree.command()
@discord.app_commands.describe(template="Template you want to convert")
async def convert(interaction: Interaction, template: discord.Attachment):
    """
    Convert a template to photocards!
    """
    await interaction.response.defer()
    response = requests.get(template.url)
    template_image = response.content

    nparr = np.frombuffer(template_image, np.uint8)
    input_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    extracted_photos = extract_photos(input_image)

    MAX_FILES_PER_MESSAGE = 9
    files = []

    for i, photo in enumerate(extracted_photos):
        _, buffer = cv2.imencode('.png', photo)
        photo_bytes = io.BytesIO(buffer)

        file = discord.File(photo_bytes, filename=f"photocard_{i}.png")
        files.append(file)

        if len(files) == MAX_FILES_PER_MESSAGE or i == len(extracted_photos) - 1:
            await interaction.followup.send(files=files)
            files = []

    if not extracted_photos:
        await interaction.followup.send("No photocards found. Try cropping the template such that only the photocards are in frame!")

@client.tree.command()
@discord.app_commands.default_permissions(manage_messages=True)
@discord.app_commands.describe(amount="Number of messages to delete")
async def purge(interaction: Interaction, amount: int):
    """
    Delete some messages from a channel!
    """
    await interaction.response.defer()
    if amount < 1 or amount > 100:
        await interaction.followup.send("Please specify an amount between 1 and 100.", ephemeral=True)
        return

    channel = interaction.channel
    await channel.purge(limit=amount + 1) 
    await interaction.followup.send(f"Deleted {amount} messages.", ephemeral=True)

@client.tree.command()
@discord.app_commands.describe(
    title="Title of the embed",
    message="Message inside the embed",
    footer="Footer text for the embed (optional)",
    color="Hex color code for the embed (optional)",
    image_url="URL of the image to embed (optional)",
    thumbnail_url="URL of the thumbnail to embed (optional)",
    message_id="ID of the message to edit (optional)")
@discord.app_commands.default_permissions(administrator=True)
async def embed(interaction: discord.Interaction, title: str, message: str, color: str = "FF2E98", footer: str = None, image_url: str = None, thumbnail_url: str = None, message_id: str = None):
    """
    Create a custom embed or edit an existing one!
    """
    await interaction.response.defer(ephemeral=True)
    try:
        color = int(color.strip("#"), 16)
    except ValueError:
        await interaction.response.send_message("Invalid color code. Please use a hex color code.", ephemeral=True)
        return

    message = message.replace("\\n", "\n")
    embed = discord.Embed(title=title, description=message, color=color)

    if footer:
        embed.set_footer(text=footer)

    if image_url:
        embed.set_image(url=image_url)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if message_id:
        channel = interaction.channel
        try:
            msg_to_edit = await channel.fetch_message(message_id)
            await msg_to_edit.edit(embed=embed)
            await interaction.response.send_message("Message edited successfully.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("Message with the given ID not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("Bot doesn't have permissions to edit the message.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Editing message failed.", ephemeral=True)
    else:
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("Embed sent successfully.", ephemeral=True)

class GiveawayView(ui.View):
    def __init__(self, message):
        super().__init__(timeout=None)
        self.message = message

    async def handle_entry(self, interaction: Interaction, entry_type: str):
        conversion = {"E":"ENTER", "R":"RATING", "T":"TIKTOK", "3": "TAG3"}
        guild = interaction.guild
        member = guild.get_member(interaction.user.id)

        discord_username = member.name
        instagram_username = member.nick if member.nick else member.display_name

        embed = self.message.embeds[0]
        field_value = embed.fields[0].value if embed.fields else ""
        user_identifier = f"({discord_username})"

        lines = field_value.split('\n') if field_value else []
        user_line_index = next((i for i, line in enumerate(lines) if user_identifier in line), None)

        if entry_type in ["R", "T", "3"] and not any(user_identifier in line for line in lines):
            await interaction.response.send_message("You need to enter the giveaway first (ENTER) before performing this action.", ephemeral=True)
            return
    
        if user_line_index is not None:
            line_parts = lines[user_line_index].split(":")
            current_entries = line_parts[1].strip() if len(line_parts) > 1 else ""
            if entry_type != "ENTER" and entry_type in current_entries:
                current_entries = current_entries.replace(entry_type, '').strip()
                response_message = f"Your **{conversion[entry_type]} ({entry_type})** entry has been removed."
            elif entry_type not in current_entries:
                current_entries += f"{entry_type}"
                response_message = f"Your entries now include: **{conversion[entry_type]} ({entry_type})**"
            else:
                response_message = f"Your Instagram username has been updated to **@{instagram_username}**."
            lines[user_line_index] = f"**@{instagram_username}** {user_identifier}: {current_entries}"
        else:
            lines.append(f"**@{instagram_username}** {user_identifier}: {entry_type}")
            response_message = f"Thank you for entering the giveaway! You may now complete bonus entries."
    
        field_value = '\n'.join(lines).strip()
        embed.clear_fields()
        embed.add_field(name="__Participants__", value=field_value if field_value else "No participants yet.", inline=False)
    
        await self.message.edit(embed=embed)
        await interaction.response.send_message(response_message, ephemeral=True)

    @ui.button(label="ENTER (+1)", style=discord.ButtonStyle.success, custom_id="default_entry")
    async def default_entry(self, interaction: Interaction, button: ui.Button):
        await self.handle_entry(interaction, "E")
        
    @ui.button(label="RATING (+1)", style=discord.ButtonStyle.primary, custom_id="rate_app")
    async def rate_app(self, interaction: Interaction, button: ui.Button):
        await self.handle_entry(interaction, "R")
        
    @ui.button(label="TIKTOK (+1)", style=discord.ButtonStyle.primary, custom_id="follow_tiktok")
    async def follow_tiktok(self, interaction: Interaction, button: ui.Button):
        await self.handle_entry(interaction, "T")

    @ui.button(label="TAG 3 (+1)", style=discord.ButtonStyle.primary, custom_id="tag_three")
    async def tag_three(self, interaction: Interaction, button: ui.Button):
        await self.handle_entry(interaction, "3")

@client.tree.command()
@discord.app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction):
    """
    Starts a new giveaway.
    """
    embed = discord.Embed(title="PCollect x 4gyuseo Giveaway", description="**__Prizes__**\n**3 Winners**\nInternational, Free Shipping\n\n**__To Enter__**\n- Follow [@4gyuseo](https://www.instagram.com/4gyuseo?igsh=MjBia3BiaXo2b25m&utm_source=qr) and [@pcollectapp](https://www.instagram.com/pcollectapp?igsh=MWFsc2toMmRxZHo3YQ%3D%3D&utm_source=qr) on Instagram\n- Like the [giveaway post](https://www.instagram.com/4gyuseo?igsh=MjBia3BiaXo2b25m&utm_source=qr) and share to story\n- Tag 3 friends in the comments\n- **MAKE YOUR SERVER NICKNAME YOUR INSTAGRAM USERNAME**\n- **CLICK THE GREEN ENTER BUTTON BELOW**\nIf you forget to change your nickname, click ENTER again and it will update your entry.\n\n**__Bonus Entries__**\n- [Rate PCollect](https://apps.apple.com/us/app/pcollect-k-pop-photocards/id6448884412) on the App Store (+1)\n- [Follow PCollect](https://www.tiktok.com/@pcollectapp?_t=8ir1lIoNe8p&_r=1) on TikTok (+1)\n- Tag 3 MORE friends in the comments (+1)\n- **CLICK THE BUTTONS BELOW WHEN YOU ARE DONE**\nWe will verify winners' entries. If you accidentally click a button, click again to undo.", color=int("FF2E98", 16))
    embed.add_field(name="__Participants__", value="", inline=False)
    giveaway_message = await interaction.channel.send(embed=embed)
    view = GiveawayView(giveaway_message)
    await giveaway_message.edit(view=view)

token = os.environ['TOKEN']
client.run(token)
