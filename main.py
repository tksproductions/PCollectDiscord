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

@client.event
async def on_ready():
  GUILDS_ID = 1191857034254102528
  client.tree.copy_global_to(guild=discord.Object(id=GUILDS_ID))
  await client.tree.sync(guild=discord.Object(id=GUILDS_ID))

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
    def __init__(self):
        super().__init__()
        self.add_item(ui.Button(label="Default Entry", style=discord.ButtonStyle.primary, custom_id="default_entry"))
        self.add_item(ui.Button(label="Rate on App Store", style=discord.ButtonStyle.primary, custom_id="rate_app"))
        self.add_item(ui.Button(label="Follow us on TikTok", style=discord.ButtonStyle.primary, custom_id="follow_tiktok"))

    async def handle_entry(self, button: ui.Button, interaction: Interaction, entry_type: str):
        channel = interaction.channel
        messages = await channel.history(limit=1).flatten()
        if messages:
            giveaway_message = messages[0]
            content = giveaway_message.content

            user_id = str(interaction.user.id)
            if user_id not in content:
                content += f"\n{user_id}: {entry_type}"
            else:
                entries = content.split(user_id)[1].split("\n")[0].strip()
                if entry_type in entries:
                    entries = entries.replace(entry_type, '').strip()
                else:
                    entries += f" | {entry_type}"
                content = content.replace(f"{user_id}: {entries.strip()}", '').strip() + f"\n{user_id}: {entries.strip()}"

            await giveaway_message.edit(content=content)
            await interaction.response.send_message(f"You have updated your entries to: {entries}", ephemeral=True)

    @ui.button(label="Default Entry", style=discord.ButtonStyle.primary, custom_id="default_entry")
    async def default_entry(self, button: ui.Button, interaction: Interaction):
        await self.handle_entry(button, interaction, "Default")

    @ui.button(label="Rate on App Store", style=discord.ButtonStyle.primary, custom_id="rate_app")
    async def rate_app(self, button: ui.Button, interaction: Interaction):
        await self.handle_entry(button, interaction, "Rate")

    @ui.button(label="Follow us on TikTok", style=discord.ButtonStyle.primary, custom_id="follow_tiktok")
    async def follow_tiktok(self, button: ui.Button, interaction: Interaction):
        await self.handle_entry(button, interaction, "TikTok")

@client.tree.command()
@discord.app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction):
    """
    Starts a new giveaway.
    """
    view = GiveawayView()
    embed = discord.Embed(title="Giveaway", description="Participate in the giveaway!")
    await interaction.channel.send(embed=embed, view=view, content="Giveaway Participants:")

token = os.environ['TOKEN']
client.run(token)
