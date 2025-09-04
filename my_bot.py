import os
import redis
import random
import string
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION ---

# Gets secrets from Railway's environment variables
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')

# Replace 123456789 with your list of admin user IDs
ADMIN_IDS = [789094994,6515017255] # Add more IDs here, separated by commas

# Connect to your Redis database
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles deep links by looking up the code in the Redis database."""
    if context.args:
        payload = context.args[0]
        file_id = db.get(payload)
        
        if file_id:
            try:
                await update.message.reply_video(
                    video=file_id, caption="Here is your media!", protect_content=True
                )
            except Exception:
                try:
                    await update.message.reply_photo(
                        photo=file_id, caption="Here is your media!", protect_content=True
                    )
                except Exception as e:
                    print(f"Error sending media: {e}")
                    await update.message.reply_text("Could not send the media.")
        else:
            await update.message.reply_text("Sorry, I don't recognize that link code.")
    else:
        await update.message.reply_text("Hello! I am your bot.")

async def handle_media_and_create_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generates a Telegram deep link, then shortens it with the InShortUrl service.
    """
    if update.message.from_user.id not in ADMIN_IDS:
        return

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.video:
        file_id = update.message.video.file_id

    if file_id:
        link_code = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
        db.set(link_code, file_id)

        bot_username = (await context.bot.get_me()).username
        telegram_deep_link = f"https://t.me/{bot_username}?start={link_code}"

        # --- NEW: Call the InShortUrl API with format=text ---
        try:
            # This is the corrected API URL format from your documentation
            api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={telegram_deep_link}&format=text"
            
            response = requests.get(api_url)
            shortened_link = response.text.strip() # .strip() removes any accidental whitespace

            # Check for empty response, which indicates an error with format=text
            if not shortened_link:
                 await update.message.reply_text("Error: Received an empty response from the ad service. Check your API key.")
                 return

            await update.message.reply_text(f"Click to reveal the full video! 🤫\n\nHere is:\n{shortened_link}")

        except Exception as e:
            await update.message.reply_text(f"An error occurred while creating the ad link: {e}")

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media_and_create_link))
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
