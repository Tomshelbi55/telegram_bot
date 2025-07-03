const TelegramBot = require('node-telegram-bot-api');
const cron = require('node-cron');
const sqlite3 = require('sqlite3').verbose();
const axios = require('axios');

// Bot token from environment variable
const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
    console.error('TELEGRAM_BOT_TOKEN environment variable is required');
    process.exit(1);
}

const bot = new TelegramBot(token, { polling: true });

// Initialize SQLite database
const db = new sqlite3.Database('quran_bot.db');

// Initialize database tables
db.serialize(() => {
    // Users table for storing user preferences
    db.run(`CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER UNIQUE,
        username TEXT,
        language TEXT DEFAULT 'en',
        tafsir_preference TEXT DEFAULT 'en.sahih',
        daily_enabled INTEGER DEFAULT 1,
        timezone TEXT DEFAULT 'UTC'
    )`);
    
    // Groups table for storing group settings
    db.run(`CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER UNIQUE,
        title TEXT,
        language TEXT DEFAULT 'en',
        tafsir_preference TEXT DEFAULT 'en.sahih',
        daily_enabled INTEGER DEFAULT 1,
        timezone TEXT DEFAULT 'UTC'
    )`);
    
    // Sent verses table to avoid repetition
    db.run(`CREATE TABLE IF NOT EXISTS sent_verses (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER,
        verse_key TEXT,
        sent_date DATE,
        UNIQUE(chat_id, verse_key, sent_date)
    )`);
});

// Available languages for translation
const LANGUAGES = {
    'en': 'English',
    'ar': 'Arabic',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'tr': 'Turkish',
    'ur': 'Urdu',
    'fa': 'Persian',
    'ru': 'Russian',
    'id': 'Indonesian',
    'bn': 'Bengali',
    'hi': 'Hindi'
};

// Available Tafsir sources
const TAFSIR_SOURCES = {
    'en.sahih': 'Sahih International',
    'en.pickthall': 'Pickthall',
    'en.yusufali': 'Yusuf Ali',
    'ar.muyassar': 'Tafsir Al-Muyassar',
    'ar.qurtubi': 'Tafsir Al-Qurtubi',
    'ar.tabari': 'Tafsir Al-Tabari',
    'en.maududi': 'Tafhim al-Qur\'an - Maududi',
    'ur.jalandhry': 'Fateh Muhammad Jalandhry',
    'tr.diyanet': 'Diyanet İşleri',
    'id.indonesian': 'Indonesian Ministry of Religion'
};

// API endpoints
const QURAN_API_BASE = 'https://api.quran.com/api/v4';
const TRANSLATION_API_BASE = 'https://api.quran.com/api/v4/translations';

// Utility functions
function getUserPreferences(chatId) {
    return new Promise((resolve, reject) => {
        db.get("SELECT * FROM users WHERE chat_id = ?", [chatId], (err, row) => {
            if (err) reject(err);
            else resolve(row || { language: 'en', tafsir_preference: 'en.sahih' });
        });
    });
}

function getGroupPreferences(chatId) {
    return new Promise((resolve, reject) => {
        db.get("SELECT * FROM groups WHERE chat_id = ?", [chatId], (err, row) => {
            if (err) reject(err);
            else resolve(row || { language: 'en', tafsir_preference: 'en.sahih' });
        });
    });
}

function saveUserPreferences(chatId, username, preferences) {
    return new Promise((resolve, reject) => {
        db.run(`INSERT OR REPLACE INTO users 
                (chat_id, username, language, tafsir_preference, daily_enabled, timezone) 
                VALUES (?, ?, ?, ?, ?, ?)`,
            [chatId, username, preferences.language, preferences.tafsir_preference, 
             preferences.daily_enabled, preferences.timezone],
            function(err) {
                if (err) reject(err);
                else resolve(this.lastID);
            });
    });
}

function saveGroupPreferences(chatId, title, preferences) {
    return new Promise((resolve, reject) => {
        db.run(`INSERT OR REPLACE INTO groups 
                (chat_id, title, language, tafsir_preference, daily_enabled, timezone) 
                VALUES (?, ?, ?, ?, ?, ?)`,
            [chatId, title, preferences.language, preferences.tafsir_preference, 
             preferences.daily_enabled, preferences.timezone],
            function(err) {
                if (err) reject(err);
                else resolve(this.lastID);
            });
    });
}

// Get random verse from Quran
async function getRandomVerse() {
    try {
        // Total verses in Quran: 6236
        const randomVerseNumber = Math.floor(Math.random() * 6236) + 1;
        
        // Get verse by number
        const response = await axios.get(`${QURAN_API_BASE}/verses/by_key/${randomVerseNumber}`);
        return response.data.verse;
    } catch (error) {
        console.error('Error fetching random verse:', error);
        // Fallback to a specific verse
        return await getVerseByKey('1:1');
    }
}

// Get verse by key (chapter:verse)
async function getVerseByKey(verseKey) {
    try {
        const response = await axios.get(`${QURAN_API_BASE}/verses/by_key/${verseKey}`);
        return response.data.verse;
    } catch (error) {
        console.error('Error fetching verse by key:', error);
        return null;
    }
}

// Get translation for a verse
async function getTranslation(verseKey, language = 'en') {
    try {
        const translationMap = {
            'en': 131, // Sahih International
            'ar': 158, // Arabic
            'es': 83,  // Spanish
            'fr': 136, // French
            'de': 27,  // German
            'tr': 77,  // Turkish
            'ur': 97,  // Urdu
            'fa': 135, // Persian
            'ru': 79,  // Russian
            'id': 134, // Indonesian
            'bn': 161, // Bengali
            'hi': 162  // Hindi
        };
        
        const translationId = translationMap[language] || 131;
        const response = await axios.get(`${TRANSLATION_API_BASE}/${translationId}/by_key/${verseKey}`);
        return response.data.translation;
    } catch (error) {
        console.error('Error fetching translation:', error);
        return null;
    }
}

// Get Tafsir for a verse
async function getTafsir(verseKey, tafsirSource = 'en.sahih') {
    try {
        const tafsirMap = {
            'en.sahih': 169,
            'en.pickthall': 168,
            'en.yusufali': 167,
            'ar.muyassar': 171,
            'ar.qurtubi': 172,
            'ar.tabari': 173,
            'en.maududi': 170,
            'ur.jalandhry': 174,
            'tr.diyanet': 175,
            'id.indonesian': 176
        };
        
        const tafsirId = tafsirMap[tafsirSource] || 169;
        const response = await axios.get(`${QURAN_API_BASE}/tafsirs/${tafsirId}/by_key/${verseKey}`);
        return response.data.tafsir;
    } catch (error) {
        console.error('Error fetching tafsir:', error);
        return null;
    }
}

// Format verse message
async function formatVerseMessage(verse, translation, tafsir, includeTafsir = true) {
    let message = `🕌 *Daily Ayah*\n\n`;
    
    // Arabic text
    message += `📖 *${verse.chapter.name_arabic} (${verse.chapter.name_simple}) ${verse.verse_number}:*\n`;
    message += `${verse.text_uthmani}\n\n`;
    
    // Translation
    if (translation) {
        message += `📚 *Translation:*\n`;
        message += `${translation.text}\n\n`;
    }
    
    // Tafsir (if requested and available)
    if (includeTafsir && tafsir) {
        message += `📝 *Tafsir:*\n`;
        const tafsirText = tafsir.text.length > 300 ? 
            tafsir.text.substring(0, 300) + '...' : tafsir.text;
        message += `${tafsirText}\n\n`;
    }
    
    message += `📍 *Reference:* ${verse.verse_key}\n`;
    message += `🔗 [Read more](https://quran.com/${verse.verse_key})`;
    
    return message;
}

// Send daily verse to user or group
async function sendDailyVerse(chatId, isGroup = false) {
    try {
        const preferences = isGroup ? 
            await getGroupPreferences(chatId) : 
            await getUserPreferences(chatId);
        
        if (!preferences.daily_enabled) return;
        
        const verse = await getRandomVerse();
        if (!verse) return;
        
        const translation = await getTranslation(verse.verse_key, preferences.language);
        const tafsir = await getTafsir(verse.verse_key, preferences.tafsir_preference);
        
        const message = await formatVerseMessage(verse, translation, tafsir);
        
        await bot.sendMessage(chatId, message, { 
            parse_mode: 'Markdown',
            disable_web_page_preview: true 
        });
        
        // Record sent verse
        db.run("INSERT OR IGNORE INTO sent_verses (chat_id, verse_key, sent_date) VALUES (?, ?, ?)",
            [chatId, verse.verse_key, new Date().toISOString().split('T')[0]]);
            
    } catch (error) {
        console.error('Error sending daily verse:', error);
    }
}

// Bot commands
bot.onText(/\/start/, async (msg) => {
    const chatId = msg.chat.id;
    const isGroup = msg.chat.type === 'group' || msg.chat.type === 'supergroup';
    
    const welcomeMessage = `
🕌 *As-salamu alaykum!*

Welcome to the Daily Quran Bot! 📖

*Available Commands:*
• /random - Get a random verse
• /settings - Configure your preferences
• /language - Change translation language
• /tafsir - Change tafsir source
• /daily - Toggle daily verses
• /help - Show this help message

*Features:*
✅ Daily Quran verses with translation
✅ Multiple languages supported
✅ Various tafsir sources available
✅ Works in groups and private chats
✅ Customizable preferences

May Allah bless you! 🤲
    `;
    
    await bot.sendMessage(chatId, welcomeMessage, { parse_mode: 'Markdown' });
    
    // Initialize user/group preferences
    if (isGroup) {
        await saveGroupPreferences(chatId, msg.chat.title, {
            language: 'en',
            tafsir_preference: 'en.sahih',
            daily_enabled: 1,
            timezone: 'UTC'
        });
    } else {
        await saveUserPreferences(chatId, msg.from.username, {
            language: 'en',
            tafsir_preference: 'en.sahih',
            daily_enabled: 1,
            timezone: 'UTC'
        });
    }
});

bot.onText(/\/random/, async (msg) => {
    const chatId = msg.chat.id;
    const isGroup = msg.chat.type === 'group' || msg.chat.type === 'supergroup';
    
    try {
        const preferences = isGroup ? 
            await getGroupPreferences(chatId) : 
            await getUserPreferences(chatId);
        
        const verse = await getRandomVerse();
        if (!verse) {
            await bot.sendMessage(chatId, "Sorry, couldn't fetch a verse right now. Please try again later.");
            return;
        }
        
        const translation = await getTranslation(verse.verse_key, preferences.language);
        const tafsir = await getTafsir(verse.verse_key, preferences.tafsir_preference);
        
        const message = await formatVerseMessage(verse, translation, tafsir);
        
        await bot.sendMessage(chatId, message, { 
            parse_mode: 'Markdown',
            disable_web_page_preview: true 
        });
        
    } catch (error) {
        console.error('Error sending random verse:', error);
        await bot.sendMessage(chatId, "Sorry, an error occurred. Please try again later.");
    }
});

bot.onText(/\/settings/, async (msg) => {
    const chatId = msg.chat.id;
    const isGroup = msg.chat.type === 'group' || msg.chat.type === 'supergroup';
    
    const preferences = isGroup ? 
        await getGroupPreferences(chatId) : 
        await getUserPreferences(chatId);
    
    const settingsMessage = `
⚙️ *Current Settings:*

📚 *Language:* ${LANGUAGES[preferences.language] || 'English'}
📖 *Tafsir Source:* ${TAFSIR_SOURCES[preferences.tafsir_preference] || 'Sahih International'}
🔔 *Daily Verses:* ${preferences.daily_enabled ? 'Enabled' : 'Disabled'}

*Commands to change settings:*
• /language - Change translation language
• /tafsir - Change tafsir source
• /daily - Toggle daily verses
    `;
    
    await bot.sendMessage(chatId, settingsMessage, { parse_mode: 'Markdown' });
});

bot.onText(/\/language/, async (msg) => {
    const chatId = msg.chat.id;
    
    let languageButtons = [];
    for (const [code, name] of Object.entries(LANGUAGES)) {
        languageButtons.push([{ text: name, callback_data: `lang_${code}` }]);
    }
    
    const keyboard = {
        inline_keyboard: languageButtons
    };
    
    await bot.sendMessage(chatId, "🌍 *Choose your preferred language:*", {
        parse_mode: 'Markdown',
        reply_markup: keyboard
    });
});

bot.onText(/\/tafsir/, async (msg) => {
    const chatId = msg.chat.id;
    
    let tafsirButtons = [];
    for (const [code, name] of Object.entries(TAFSIR_SOURCES)) {
        tafsirButtons.push([{ text: name, callback_data: `tafsir_${code}` }]);
    }
    
    const keyboard = {
        inline_keyboard: tafsirButtons
    };
    
    await bot.sendMessage(chatId, "📚 *Choose your preferred tafsir source:*", {
        parse_mode: 'Markdown',
        reply_markup: keyboard
    });
});

bot.onText(/\/daily/, async (msg) => {
    const chatId = msg.chat.id;
    const isGroup = msg.chat.type === 'group' || msg.chat.type === 'supergroup';
    
    const preferences = isGroup ? 
        await getGroupPreferences(chatId) : 
        await getUserPreferences(chatId);
    
    const newStatus = preferences.daily_enabled ? 0 : 1;
    
    if (isGroup) {
        await saveGroupPreferences(chatId, msg.chat.title, {
            ...preferences,
            daily_enabled: newStatus
        });
    } else {
        await saveUserPreferences(chatId, msg.from.username, {
            ...preferences,
            daily_enabled: newStatus
        });
    }
    
    const statusText = newStatus ? 'enabled' : 'disabled';
    await bot.sendMessage(chatId, `🔔 Daily verses have been *${statusText}*!`, { 
        parse_mode: 'Markdown' 
    });
});

bot.onText(/\/help/, async (msg) => {
    const chatId = msg.chat.id;
    
    const helpMessage = `
🤖 *Quran Daily Bot Help*

*Commands:*
• /start - Initialize the bot
• /random - Get a random Quran verse
• /settings - View current settings
• /language - Change translation language
• /tafsir - Change tafsir commentary source
• /daily - Toggle daily verse notifications
• /help - Show this help message

*Features:*
📖 Daily Quran verses sent automatically
🌍 Multiple translation languages
📚 Various tafsir sources
👥 Works in groups and private chats
⚙️ Customizable user preferences

*Languages Supported:*
English, Arabic, Spanish, French, German, Turkish, Urdu, Persian, Russian, Indonesian, Bengali, Hindi

*Need help?* Contact the bot administrator.

May Allah guide us all! 🤲
    `;
    
    await bot.sendMessage(chatId, helpMessage, { parse_mode: 'Markdown' });
});

// Handle callback queries (inline keyboard responses)
bot.on('callback_query', async (query) => {
    const chatId = query.message.chat.id;
    const isGroup = query.message.chat.type === 'group' || query.message.chat.type === 'supergroup';
    const data = query.data;
    
    if (data.startsWith('lang_')) {
        const langCode = data.replace('lang_', '');
        const preferences = isGroup ? 
            await getGroupPreferences(chatId) : 
            await getUserPreferences(chatId);
        
        if (isGroup) {
            await saveGroupPreferences(chatId, query.message.chat.title, {
                ...preferences,
                language: langCode
            });
        } else {
            await saveUserPreferences(chatId, query.from.username, {
                ...preferences,
                language: langCode
            });
        }
        
        await bot.answerCallbackQuery(query.id, { 
            text: `Language changed to ${LANGUAGES[langCode]}` 
        });
        
        await bot.editMessageText(
            `✅ Language updated to *${LANGUAGES[langCode]}*`,
            {
                chat_id: chatId,
                message_id: query.message.message_id,
                parse_mode: 'Markdown'
            }
        );
    }
    
    if (data.startsWith('tafsir_')) {
        const tafsirCode = data.replace('tafsir_', '');
        const preferences = isGroup ? 
            await getGroupPreferences(chatId) : 
            await getUserPreferences(chatId);
        
        if (isGroup) {
            await saveGroupPreferences(chatId, query.message.chat.title, {
                ...preferences,
                tafsir_preference: tafsirCode
            });
        } else {
            await saveUserPreferences(chatId, query.from.username, {
                ...preferences,
                tafsir_preference: tafsirCode
            });
        }
        
        await bot.answerCallbackQuery(query.id, { 
            text: `Tafsir source changed to ${TAFSIR_SOURCES[tafsirCode]}` 
        });
        
        await bot.editMessageText(
            `✅ Tafsir source updated to *${TAFSIR_SOURCES[tafsirCode]}*`,
            {
                chat_id: chatId,
                message_id: query.message.message_id,
                parse_mode: 'Markdown'
            }
        );
    }
});

// Schedule daily verses - runs every day at 8 AM
cron.schedule('0 8 * * *', async () => {
    console.log('Sending daily verses...');
    
    // Send to all users
    db.all("SELECT chat_id FROM users WHERE daily_enabled = 1", (err, users) => {
        if (err) {
            console.error('Error fetching users:', err);
            return;
        }
        
        users.forEach(async (user) => {
            await sendDailyVerse(user.chat_id, false);
        });
    });
    
    // Send to all groups
    db.all("SELECT chat_id FROM groups WHERE daily_enabled = 1", (err, groups) => {
        if (err) {
            console.error('Error fetching groups:', err);
            return;
        }
        
        groups.forEach(async (group) => {
            await sendDailyVerse(group.chat_id, true);
        });
    });
});

// Error handling
bot.on('error', (error) => {
    console.error('Bot error:', error);
});

bot.on('polling_error', (error) => {
    console.error('Polling error:', error);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

// Health check endpoint for Railway
const http = require('http');
const port = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
    if (req.url === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }));
    } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not found');
    }
});

server.listen(port, () => {
    console.log(`Health check server running on port ${port}`);
});

console.log('🤖 Quran Daily Bot is running...');
console.log('Bot features:');
console.log('✅ Daily verse delivery');
console.log('✅ Random verse on command');
console.log('✅ Multi-language support');
console.log('✅ Tafsir integration');
console.log('✅ Group and private chat support');
console.log('✅ User preferences management');