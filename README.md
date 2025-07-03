# Quran Daily Bot

A comprehensive Telegram bot that sends daily Quran verses with translations and tafsir commentary in multiple languages.

## Features

- 🕌 **Daily Quran Verses**: Automatically sends verses at 8 AM daily
- 🌍 **Multi-language Support**: 12 languages including English, Arabic, Spanish, French, German, Turkish, Urdu, Persian, Russian, Indonesian, Bengali, and Hindi
- 📚 **Tafsir Integration**: Multiple tafsir sources available
- 👥 **Group & Private Chat**: Works in both group chats and private messages
- ⚙️ **User Preferences**: Customizable settings for each user/group
- 🔄 **Random Verses**: Get random verses on command
- 💾 **SQLite Database**: Stores user preferences and prevents duplicate daily verses

## Commands

- `/start` - Initialize the bot and see welcome message
- `/random` - Get a random Quran verse
- `/settings` - View current settings
- `/language` - Change translation language
- `/tafsir` - Change tafsir commentary source
- `/daily` - Toggle daily verse notifications
- `/help` - Show help information

## Setup for Railway Deployment

### 1. Prerequisites

- Create a Telegram bot through [@BotFather](https://t.me/BotFather)
- Get your bot token
- Have a Railway account

### 2. Environment Variables

Set the following environment variable in Railway:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Deploy to Railway

1. Push your code to a GitHub repository
2. Connect Railway to your GitHub repository
3. Add the environment variable in Railway dashboard
4. Deploy the project

### 4. Local Development

```bash
# Install dependencies
npm install

# Set environment variable
export TELEGRAM_BOT_TOKEN=your_bot_token_here

# Run the bot
npm start

# Or for development with auto-reload
npm run dev
```

## Database Schema

The bot uses SQLite with three tables:

- **users**: Stores individual user preferences
- **groups**: Stores group chat settings
- **sent_verses**: Tracks sent verses to avoid duplicates

## API Sources

- **Quran API**: [api.quran.com](https://api.quran.com) for verses and translations
- **Tafsir API**: Multiple sources for commentary

## Supported Languages

- English (en)
- Arabic (ar)
- Spanish (es)
- French (fr)
- German (de)
- Turkish (tr)
- Urdu (ur)
- Persian (fa)
- Russian (ru)
- Indonesian (id)
- Bengali (bn)
- Hindi (hi)

## Tafsir Sources

- Sahih International
- Pickthall
- Yusuf Ali
- Tafsir Al-Muyassar
- Tafsir Al-Qurtubi
- Tafsir Al-Tabari
- Tafhim al-Qur'an - Maududi
- And more...

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## Support

For support or questions, please create an issue in the repository.