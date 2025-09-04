import os
import redis
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- SECTION 1: CONFIGURATION ---

# Gets the token and Redis URL from Railway's environment variables
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')

# Replace 123456789 with your actual Telegram User ID.
ADMIN_IDS = [789094994,6515017255]



# Connect to your Redis database
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles deep links by looking up the code in the Redis database."""
    if context.args:
        payload = context.args[0]
        
        # Check if the payload code exists in our Redis database
        file_id = db.get(payload) # Fetches the file_id associated with the payload
        
        if file_id:
            # Note: We don't know if it's a photo or video, so we try video first.
            # A more advanced bot could store the media type as well.
            try:
                await update.message.reply_video(video=file_id, caption="Here is your media!",protect_content=True)
            except Exception:
                try:
                    await update.message.reply_photo(photo=file_id, caption="Here is your media!",protect_content=True)
                except Exception as e:
                    print(e)
                    await update.message.reply_text("Could not send the media.")
        else:
            await update.message.reply_text("Sorry, I don't recognize that link code.")
    else:
        await update.message.reply_text("Hello! I am your bot.")

async def add_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves a file_id to the database with a custom link code. Admin only."""
    # Check if the user is the admin
    if update.message.from_user.id != ADMIN_IDS:
        return # Ignore non-admins

    try:
        # Check if this command is a reply to a message with media
        replied_message = update.message.reply_to_message
        if not replied_message:
            await update.message.reply_text("Please reply to a photo or video to use this command.")
            return

        file_id = None
        if replied_message.photo:
            file_id = replied_message.photo[-1].file_id
        elif replied_message.video:
            file_id = replied_message.video.file_id
        else:
            await update.message.reply_text("You can only use this command when replying to a photo or video.")
            return

        # Get the unique link code from the command, e.g., /add my_cool_video
        link_code = context.args[0]

        # Save the new entry to the Redis database
        db.set(link_code, file_id)

        bot_username = (await context.bot.get_me()).username
        final_link = f"https://t.me/{bot_username}?start={link_code}"

        await update.message.reply_text(f"✅ Link created!\n\nYour shareable link is:\n{final_link}")

    except (IndexError, TypeError):
        await update.message.reply_text("Usage: Reply to a photo/video and use the command `/add <unique_link_code>`")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_media))

    # Start the Bot
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
