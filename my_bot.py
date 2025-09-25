import os
import random
import string
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from replit import db # <-- Use Replit's built-in database instead of Redis
from flask import Flask
from threading import Thread

# --- SECTION 1: CONFIGURATION ---

# Gets secrets from Replit's "Secrets" tab
TOKEN = os.environ.get('TOKEN')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')

# Add your admin User IDs here
ADMIN_IDS = [789094994] 

# --- SECTION 2: BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles deep links by looking up the code in the Replit database."""
    if context.args:
        payload = context.args[0]
        # Check if the payload code exists in our database
        if payload in db:
            file_id = db[payload]
            try:
                await update.message.reply_video(video=file_id, caption="Here is your media!", protect_content=True)
            except Exception:
                await update.message.reply_photo(photo=file_id, caption="Here is your media!", protect_content=True)
        else:
            await update.message.reply_text("Sorry, I don't recognize that link code.")
    else:
        await update.message.reply_text("Hello! I am your bot.")

async def handle_media_and_create_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When an admin sends media, generates a random link, saves it, and replies with the monetized link."""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.video:
        file_id = update.message.video.file_id

    if file_id:
        link_code = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
        
        # Save the new code and file_id to the Replit database
        db[link_code] = file_id

        bot_username = (await context.bot.get_me()).username
        telegram_deep_link = f"https://t.me/{bot_username}?start={link_code}"

        try:
            api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={telegram_deep_link}&format=text"
            response = requests.get(api_url)
            shortened_link = response.text.strip()
            
            if not shortened_link:
                 await update.message.reply_text("Error: Empty response from ad service.")
                 return

            await update.message.reply_text(f"✅ Monetized link created!\n\nYour shareable link is:\n{shortened_link}")
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {e}")

# --- SECTION 3: KEEP-ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ------------------------------------

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media_and_create_link))
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    keep_alive()
    main()
