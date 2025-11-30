# image-captioner

A Discord bot that explains images uploaded by users.

## Setup

### Prerequisites

1. Python
2. Discord Bot Token
3. OpenAI API Key

### Installation

1. Clone or download this repository

2. Create a `.env` file based on `.env.example`:

   ```bash
   cp .env.example .env
   ```

3. Fill in your credentials in `.env`:

   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

### Creating a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" tab and click "Add Bot"
4. Enable the Message Content Intent bot privilege
5. Copy the bot token to your `.env` file

### Inviting the Bot to Your Server

1. In the Discord Developer Portal, go to "Installation" → "Install Link"
2. Copy the generated URL and use it to invite the bot to your server or add it to your user globally

### Running the Bot

Run with uv:

```bash
uv run image-captioner
```

## Usage

Once the bot is running and invited to your server or added to your user globally, right click on an image and go to "More" → "Apps" → "Explain Image".

## Help

Message tetraspace (#tetraspace) on Discord
