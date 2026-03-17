import os
import asyncio
import discord
import openrouter
import openrouter.errors
from dotenv import load_dotenv
import aiohttp
import base64
import logging
import traceback

MAX_IMAGE_DIM = 1024

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


@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} servers")
    try:
        await bot.http.bulk_upsert_global_commands(bot.user.id, payload=[])
        logger.info("Successfully deleted all application commands.")
    except Exception as e:
        logger.error(f"Failed to delete application commands: {e}")


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


async def caption_image(base64_image, media_type):
    response = client.chat.send(
        model="anthropic/claude-sonnet-4.6",
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
        http_headers={
            "HTTP-Referer": "https://github.com/TetraspaceW/image-captioner",
            "X-Title": "image-captioner",
        },
    )
    return response.choices[0].message.content


@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Find all image attachments in the message
    images = [
        attachment
        for attachment in message.attachments
        if attachment.content_type and attachment.content_type.startswith("image/")
    ]

    if not images:
        return

    # Wait two seconds to make sure the message isn't instantly deleted
    await asyncio.sleep(2)
    try:
        await message.channel.fetch_message(message.id)
    except discord.NotFound:
        logger.info(f"Message {message.id} was deleted before processing")
        return

    logger.info(
        f"Found {len(images)} image(s) in message {message.id} from {message.author}"
    )

    async with message.channel.typing():
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

                # Download a low-res version of the image from Discord's CDN
                resized_url = (
                    f"{image.proxy_url}?width={MAX_IMAGE_DIM}&height={MAX_IMAGE_DIM}"
                )
                async with aiohttp.ClientSession() as session:
                    async with session.get(resized_url) as resp:
                        image_data = await resp.read()
                logger.info(
                    f"Downloaded {len(image_data)} bytes of image data (resized)"
                )

                # Convert image to base64
                base64_image = base64.b64encode(image_data).decode("utf-8")

                # Send to OpenRouter for captioning
                logger.info(f"Sending request to OpenRouter for image {idx + 1}...")
                media_type = image.content_type
                try:
                    explanation = await caption_image(base64_image, media_type)
                except openrouter.errors.OpenRouterError as e:
                    if media_type == "image/webp":
                        logger.warning(
                            f"Provider error with webp for image {idx + 1}, retrying as image/png: {e}"
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
                    f"Request params: model=anthropic/claude-sonnet-4.6, max_tokens=500, "
                    f"image_content_type={image.content_type}, image_size={image.size}, "
                    f"base64_length={len(base64_image)}"
                )
                traceback.print_exc()
                await message.add_reaction("\u26a0\ufe0f")
                return

            except Exception as e:
                logger.error(f"Error processing image {idx + 1}: {e}")
                traceback.print_exc()
                await message.add_reaction("\u26a0\ufe0f")
                return

        # Send as a plain text reply
        reply = "\n\n".join(explanations)
        # Discord has a 2000 char limit
        if len(reply) > 2000:
            reply = reply[:1997] + "..."

        try:
            await message.reply("Image caption: " + reply)
            logger.info("Successfully sent reply")
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            traceback.print_exc()


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
