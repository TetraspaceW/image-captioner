import os
import discord
from discord import app_commands
from discord.ext import commands
import openrouter
from dotenv import load_dotenv
import base64
import logging

# Load environment variables
load_dotenv()

# Configure OpenRouter
client = openrouter.OpenRouter(
    api_key=os.getenv('OPENROUTER_API_KEY')
)

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Context menu (must be defined outside the class)
@app_commands.context_menu(name="Explain Image")
async def explain_image_context(interaction: discord.Interaction, message: discord.Message):
    """Explain images using AI (right-click on a message)"""
    
    logger.info(f"Context menu triggered by {interaction.user} on message {message.id}")
    
    try:
        # Find all image attachments in the message
        images = []
        for i, attachment in enumerate(message.attachments):
            logger.info(f"Attachment {i}: {attachment.filename}, content_type: {attachment.content_type}")
            if attachment.content_type and attachment.content_type.startswith('image/'):
                images.append(attachment)
        
        if not images:
            logger.error("Error: No images found in message")
            await interaction.response.send_message("This message doesn't contain any images.", ephemeral=True)
            return
        
        logger.info(f"Found {len(images)} image(s)")
        
        # Defer the response since this might take a while
        await interaction.response.defer()
        logger.info("Response deferred")
        
        explanations = []
        
        # Process each image
        for idx, image in enumerate(images):
            logger.info(f"Processing image {idx + 1}/{len(images)}: {image.filename}, size: {image.size}")
            
            try:
                # Download the image
                image_data = await image.read()
                logger.info(f"Downloaded {len(image_data)} bytes of image data")
                
                # Convert image to base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Prepare the message for OpenRouter
                logger.info(f"Sending request to OpenRouter for image {idx + 1}...")
                response = client.chat.send(
                    model="anthropic/claude-opus-4.5",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Hi! The user is visually impaired and wants you to give a caption that fully explains what's in this image."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{image.content_type};base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500
                )
                
                explanation = response.choices[0].message.content
                logger.info(f"Received response for image {idx + 1}")
                
                # Create an embed for this image
                embed = discord.Embed(
                    title=f"🖼️ Image {idx + 1} Explanation",
                    description=explanation,
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=image.url)
                embed.set_footer(text=f"File: {image.filename}")
                
                explanations.append(embed)
                
            except Exception as e:
                logger.error(f"Error processing image {idx + 1}: {e}")
                # Create an error embed for this image
                error_embed = discord.Embed(
                    title=f"❌ Image {idx + 1} Error",
                    description=f"Failed to analyze {image.filename}: {str(e)}",
                    color=discord.Color.red()
                )
                error_embed.set_footer(text=f"File: {image.filename}")
                explanations.append(error_embed)
        
        # Send all explanations
        logger.info(f"Sending {len(explanations)} embed(s)")
        if len(explanations) == 1:
            await interaction.followup.send(embed=explanations[0])
        else:
            # Send multiple embeds in one message
            await interaction.followup.send(embeds=explanations)
        
        logger.info("Successfully sent response(s)")
            
    except Exception as e:
        logger.error(f"Unexpected error in explain command: {e}")
        import traceback
        traceback.print_exc()
        try:
            await interaction.response.send_message(f"An unexpected error occurred: {str(e)}", ephemeral=True)
        except:
            logger.error("Could not send error response to user")

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} servers')
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_disconnect():
    logger.info("Bot disconnected from Discord")

@bot.event
async def on_resumed():
    logger.info("Bot reconnected to Discord")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Error in {event}: {args} {kwargs}")
    import traceback
    traceback.print_exc()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide all required arguments.")
    else:
        logger.error(f"An error occurred: {str(error)}")

async def setup(bot):
    # Add the context menu to the bot tree
    bot.tree.add_command(explain_image_context)

def main():
    """Main entry point for the bot"""
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.error("Error: DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    async def run_bot():
        async with bot:
            await setup(bot)
            await bot.start(TOKEN)
    
    import asyncio
    asyncio.run(run_bot())

# Run the bot
if __name__ == "__main__":
    main()
