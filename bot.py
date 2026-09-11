import os
import asyncio
import json
import discord
from discord import app_commands
import openrouter
import openrouter.errors
from dotenv import load_dotenv
import aiohttp
import base64
import logging
import traceback
from typing import Protocol
from urllib.parse import urlsplit

# Load environment variables
load_dotenv()

# Configure OpenRouter
client = openrouter.OpenRouter(api_key=os.getenv("OPENROUTER_API_KEY"))

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Guild config
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "guild_config.json"
)


def load_guild_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_guild_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_guild_mode(guild_id):
    """Return the mode for a guild: 'auto' or 'command'. Default is 'auto'."""
    config = load_guild_config()
    return config.get(str(guild_id), "auto")


@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} servers")
    try:
        await tree.sync()
        logger.info("Successfully synced application commands.")
    except Exception as e:
        logger.error(f"Failed to sync application commands: {e}")


@bot.event
async def on_disconnect():
    logger.info("Bot disconnected from Discord")


@bot.event
async def on_resumed():
    logger.info("Bot reconnected to Discord")


@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {args} {kwargs}")
    traceback.print_exc()


def format_explanation(explanation: str):
    lines = [line for line in explanation.split("\n") if line.strip()]
    return "\n".join([f"-# > {line}" for line in lines])


def build_replies(explanations: list[str]) -> list[str]:
    replies = []
    for i, exp in enumerate(explanations, 1):
        if len(explanations) == 1:
            reply = "Image caption:\n" + format_explanation(exp)
        else:
            reply = f"Image {i} caption:\n" + format_explanation(exp)
        # Discord has a 2000 char limit
        if len(reply) > 2000:
            reply = reply[:1997] + "..."
        replies.append(reply)
    return replies


class ImageSource(Protocol):
    filename: str
    description: str | None
    content_type: str
    size: int

    async def read(self) -> bytes: ...


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff")


class EmbedImage:
    """Lightweight wrapper around an embed image URL to match the Attachment interface."""

    def __init__(self, url: str, filename: str = "embed_image"):
        self.url = url
        self.filename = filename
        self.description = None
        self.content_type = "image/png"
        self.size = 0
        self._data = None

    async def read(self) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as resp:
                resp.raise_for_status()
                ct = resp.content_type or ""
                if ct.startswith("image/"):
                    self.content_type = ct
                self._data = await resp.read()
                self.size = len(self._data)
                return self._data


def _collect_image_attachments(attachments) -> list[ImageSource]:
    return [
        attachment
        for attachment in attachments
        if attachment.content_type and attachment.content_type.startswith("image/")
    ]


def _collect_embed_images(embeds) -> list[ImageSource]:
    images: list[ImageSource] = []
    for embed in embeds:
        logger.info(f"Embed: type={embed.type}, content={embed.to_dict()}")
        if embed.image and embed.image.url:
            url = embed.image.url
            if not any(ext in urlsplit(url).path.lower() for ext in IMAGE_EXTENSIONS):
                continue
            filename = urlsplit(url).path.split("/")[-1]
            images.append(EmbedImage(url, filename=filename))
        elif embed.thumbnail and embed.thumbnail.url:
            url = embed.thumbnail.url
            if not any(ext in urlsplit(url).path.lower() for ext in IMAGE_EXTENSIONS):
                continue
            filename = urlsplit(url).path.split("/")[-1]
            images.append(EmbedImage(url, filename=filename))
    return images


def collect_images(message: discord.Message) -> list[ImageSource]:
    """Collect image attachments and embed images from a message, including forwarded messages."""
    images: list[ImageSource] = []
    images.extend(_collect_image_attachments(message.attachments))
    images.extend(_collect_embed_images(message.embeds))
    for snapshot in message.message_snapshots:
        images.extend(_collect_image_attachments(snapshot.attachments))
        images.extend(_collect_embed_images(snapshot.embeds))
    return images


async def caption_image(base64_image, media_type):
    response = await asyncio.to_thread(
        client.chat.send,
        model="google/gemini-flash-latest",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hi! The user is visually impaired or a language model and wants you to give a caption that fully explains what's in this image. Make it plain and factual. Don't use special formatting.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
        reasoning={"effort": "minimal", "exclude": True},
        http_headers={
            "HTTP-Referer": "https://github.com/TetraspaceW/image-captioner",
            "X-Title": "image-captioner",
        },
    )
    return response.choices[0].message.content


async def caption_images_from_message(images: list[ImageSource]):
    """Caption a list of image attachments. Returns (explanations, error_occurred)."""
    explanations = []

    for idx, image in enumerate(images):
        logger.info(
            f"Processing image {idx + 1}/{len(images)}: {image.filename}, size: {image.size}"
        )

        try:
            # If the image has alt text, use it directly
            if image.description:
                logger.info(f"Image {idx + 1} has alt text, using that")
                explanations.append(image.description)
                continue

            # Download the image
            image_data = await image.read()
            logger.info(f"Downloaded {len(image_data)} bytes of image data")

            # Convert image to base64
            # We send base64 because the discord CDN doesn't like direct requests
            base64_image = base64.b64encode(image_data).decode("utf-8")

            # Send to OpenRouter for captioning
            logger.info(f"Sending request to OpenRouter for image {idx + 1}...")
            media_type = image.content_type
            try:
                explanation = await caption_image(base64_image, media_type)
            except openrouter.errors.OpenRouterError as e:
                # Discord will sometimes send things openrouter things are pngs as non-pngs
                if media_type != "image/png":
                    logger.warning(
                        f"Provider error with {media_type} for image {idx + 1}, retrying as image/png: {e}"
                    )
                    explanation = await caption_image(base64_image, "image/png")
                else:
                    raise

            logger.info(f"Received response for image {idx + 1}")
            explanations.append(explanation)

        except openrouter.errors.OpenRouterError as e:
            logger.error(f"Provider error for image {idx + 1}: {e}")
            logger.error(f"Error body: {getattr(e, 'body', None)}")
            logger.error(
                f"Status code: {getattr(e, 'raw_response', None) and e.raw_response.status_code}"
            )
            logger.error(
                f"Request params: model=google/gemini-flash-latest, max_tokens=500, "
                f"image_content_type={image.content_type}, image_size={image.size}, "
                f"base64_length={len(base64_image)}"
            )
            traceback.print_exc()
            return None, True

        except Exception as e:
            logger.error(f"Error processing image {idx + 1}: {e}")
            traceback.print_exc()
            return None, True

    return explanations, False


@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Only auto-caption in guilds set to 'auto' mode
    if message.guild and get_guild_mode(message.guild.id) != "auto":
        return

    # Wait two seconds for embeds to populate and to make sure the message isn't instantly deleted
    await asyncio.sleep(2)
    try:
        message = await message.channel.fetch_message(message.id)
    except discord.NotFound:
        logger.info(f"Message {message.id} was deleted before processing")
        return

    # Find all image attachments and embed images in the message
    images = collect_images(message)

    if not images:
        return

    logger.info(
        f"Found {len(images)} image(s) in message {message.id} from {message.author}"
    )

    async with message.channel.typing():
        explanations, error = await caption_images_from_message(images)

        if error:
            await message.add_reaction("\u26a0\ufe0f")
            return

        # Send as plain text replies
        replies = build_replies(explanations)

        try:
            for reply in replies:
                await message.reply(reply)
            logger.info("Successfully sent reply")
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            traceback.print_exc()


@tree.command(
    name="captioner", description="Configure image captioner mode for this server"
)
@app_commands.describe(
    mode="auto: caption all images automatically, command: only caption via the Describe Images command"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="auto", value="auto"),
        app_commands.Choice(name="command", value="command"),
    ]
)
async def captioner_config(
    interaction: discord.Interaction, mode: app_commands.Choice[str]
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "You need the Manage Server permission to change this setting.",
            ephemeral=True,
        )
        return

    config = load_guild_config()
    config[str(interaction.guild_id)] = mode.value
    save_guild_config(config)

    if mode.value == "auto":
        description = "I will now automatically caption all images in this server."
    else:
        description = "I will now only caption images when asked via the **Describe Images** command (right-click a message → Apps)."

    await interaction.response.send_message(description, ephemeral=True)
    logger.info(f"Guild {interaction.guild_id} set captioner mode to '{mode.value}'")


@tree.context_menu(name="Describe Images")
async def describe_images(interaction: discord.Interaction, message: discord.Message):
    images = collect_images(message)

    if not images:
        await interaction.response.send_message(
            "This message has no images.", ephemeral=True
        )
        return

    await interaction.response.defer()

    logger.info(
        f"Describe command: {len(images)} image(s) in message {message.id} from {message.author}"
    )

    explanations, error = await caption_images_from_message(images)

    if error:
        await interaction.followup.send(
            "Something went wrong while captioning the images."
        )
        return

    replies = build_replies(explanations)
    for reply in replies:
        await interaction.followup.send(reply)


def main():
    """Main entry point for the bot"""
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("Error: DISCORD_TOKEN not found in environment variables!")
        exit(1)

    bot.run(TOKEN)


# Run the bot
if __name__ == "__main__":
    main()
