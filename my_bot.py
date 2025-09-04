import os
import redis
import random
import string
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION ---

# Gets the token and Redis URL from Railway's environment variables
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')

# Replace 123456789 with your list of admin user IDs
ADMIN_IDS = [789094994] # Add more IDs here, separated by commas

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
                    video=file_id, 
                    caption="Here is your media!", 
                    protect_content=True
                )
            except Exception:
                try:
                    await update.message.reply_photo(
                        photo=file_id, 
                        caption="Here is your media!", 
                        protect_content=True
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
    When an admin sends media, this function automatically generates a random link code,
    saves it to the database, and replies with the final shareable link.
    """
    # Check if the user is in our list of admins
    if update.message.from_user.id not in ADMIN_IDS:
        return  # Ignore non-admins

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.video:
        file_id = update.message.video.file_id

    if file_id:
        # Generate a short, random code for the link
        link_code = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
        
        # Save the new code and file_id to the Redis database
        db.set(link_code, file_id)

        bot_username = (await context.bot.get_me()).username
        final_link = f"https://t.me/{bot_username}?start={link_code}"

        await update.message.reply_text(f"✅ Link created!\n\nYour shareable link is:\n{final_link}")

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    # This new handler replaces the /add command for admins
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media_and_create_link))

    # Start the Bot
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
