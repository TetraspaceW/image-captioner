# Discord Image Explainer Bot

A Discord bot that uses GPT-4 Vision to explain images uploaded by users.

## Features

- **/explain** slash command that analyzes images using AI
- Detailed image descriptions with context and notable details
- Beautiful embed responses with thumbnails
- Error handling and validation

## Setup

### Prerequisites

1. Python 3.8 or higher
2. Discord Bot Token
3. OpenAI API Key

### Installation

1. Clone or download this repository
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on `.env.example`:

   ```bash
   cp .env.example .env
   ```

4. Fill in your credentials in `.env`:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Creating a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" tab and click "Add Bot"
4. Enable the following bot privileges:
   - Message Content Intent
   - Attachments Intent
5. Copy the bot token to your `.env` file

### Inviting the Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" → "URL Generator"
2. Select these scopes:
   - `bot`
   - `applications.commands`
3. Select these bot permissions:
   - Send Messages
   - Read Message History
   - Attach Files
   - Use Application Commands
4. Copy the generated URL and use it to invite the bot to your server

### Running the Bot

```bash
python bot.py
```

## Usage

Once the bot is running and invited to your server:

1. Type `/explain` in any channel
2. Upload an image when prompted
3. The bot will analyze the image and provide a detailed explanation

## Example

```
User: /explain
[uploads image of a sunset over mountains]

Bot: [Responds with detailed description of the sunset scene]
```

## Configuration Options

The bot uses environment variables for configuration:

- `DISCORD_TOKEN`: Your Discord bot token (required)
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `BOT_PREFIX`: Prefix for text commands (defaults to "!")
- `GUILD_ID`: Server ID for faster command syncing (optional)

## Troubleshooting

### Common Issues

1. **"DISCORD_TOKEN not found"**: Make sure your `.env` file is properly configured
2. **"Failed to sync commands"**: The bot may need administrator permissions or you may need to specify a GUILD_ID
3. **"An error occurred while analyzing the image"**: Check your OpenAI API key and make sure you have sufficient credits

### Getting Help

- Make sure all intents are enabled in the Discord Developer Portal
- Verify the bot has the necessary permissions in your server
- Check that your OpenAI API key is valid and has credits available

## License

MIT License
