import os
import tempfile
import logging
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Please set the TELEGRAM_BOT_TOKEN environment variable")

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Send me a YouTube link, and I'll let you pick the quality to download."
    )

def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    if 'youtu' not in url:
        update.message.reply_text("Please send a valid YouTube URL.")
        return

    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            update.message.reply_text(f"Failed to fetch info: {e}")
            return

        formats = info.get('formats', [])

    # Filter video formats with video + audio or video only, exclude duplicates by format_id
    seen = set()
    buttons = []
    for f in formats:
        if f['format_id'] in seen:
            continue
        seen.add(f['format_id'])
        # Show only video formats with height info or audio only
        if f.get('vcodec') != 'none':
            label = f"{f.get('format_note','')} - {f.get('ext')} - {f.get('fps','')}fps"
            buttons.append([InlineKeyboardButton(label, callback_data=f"download|{url}|{f['format_id']}")])
    # Add audio only option separately
    buttons.append([InlineKeyboardButton("Audio only (best)", callback_data=f"download|{url}|bestaudio")])

    reply_markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text("Select quality:", reply_markup=reply_markup)

def make_hook(chat_id, message_id, context):
    def hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            text = f"Downloading... {percent}"
            try:
                context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
            except Exception:
                pass  # Ignore edit errors (e.g., too frequent)
    return hook

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data.split('|')
    if len(data) != 3 or data[0] != 'download':
        query.answer()
        return
    _, url, fmt = data
    chat_id = query.message.chat.id
    msg_id = query.message.message_id

    context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="Starting download...")

    def download_and_send():
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            ydl_opts = {
                'format': fmt,
                'outtmpl': '%(title)s.%(ext)s',
                'progress_hooks': [make_hook(chat_id, msg_id, context)],
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                with open(filename, 'rb') as f:
                    context.bot.send_video(chat_id=chat_id, video=f)
                context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Download error: {e}")
                context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=f"Failed: {e}")

    threading.Thread(target=download_and_send, daemon=True).start()
    query.answer()

def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
