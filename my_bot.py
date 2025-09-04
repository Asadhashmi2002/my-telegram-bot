import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION (EDIT THESE) ---

# This gets the token from your hosting environment's secrets. DO NOT WRITE YOUR TOKEN HERE.
TOKEN = os.environ.get('TOKEN')

# Replace 123456789 with your actual Telegram User ID.
ADMIN_USER_ID = 789094994

# Your simple "database" for videos.
# Add new entries here. The key is the link code, the value is the file_id.
VIDEO_DATABASE = {
    "bunny_video": "AgACAgUAAx0Efz3f2gACAulnB1b-q5lUaG_32J-M9l9zZ8hYAAIosDEb-zrwV32pCq8f8tZRAQADAgADeAADMAQ",
    # Example: "my_cool_video": "REPLACE_WITH_VIDEO_FILE_ID",
}

# Your simple "database" for photos.
PHOTO_DATABASE = {
    "sample_photo": "AgACAgUAAx0Efz3f2gACAupnB1dAq_P5h85zGUeYk8hX5xqKAAIpsDEb-zrwV7r9bW9pD1uWAQADAgADeAADMAQ",
    # Example: "my_cool_photo": "REPLACE_WITH_PHOTO_FILE_ID",
}

# --- SECTION 2: BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command and deep links for photos and videos."""
    if context.args:
        payload = context.args[0]
        
        # Check if the payload is in the VIDEO_DATABASE
        if payload in VIDEO_DATABASE:
            file_id = VIDEO_DATABASE[payload]
            await update.message.reply_video(video=file_id, caption="Here's your video!")
            
        # Check if the payload is in the PHOTO_DATABASE
        elif payload in PHOTO_DATABASE:
            file_id = PHOTO_DATABASE[payload]
            await update.message.reply_photo(photo=file_id, caption="Here's your photo!")
            
        else:
            await update.message.reply_text("Sorry, I don't recognize that link code.")
    else:
        # Default message if someone just types /start
        await update.message.reply_text("Hello! I am your bot. Use a special link to get media.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles photo/video messages. If sent by the admin, it replies with the file_id.
    """
    # Check if the message is from the admin
    if update.message.from_user.id == ADMIN_USER_ID:
        file_id = None
        media_type = ""
        
        if update.message.video:
            file_id = update.message.video.file_id
            media_type = "Video"
        elif update.message.photo:
            # Photos have multiple sizes, we take the largest one
            file_id = update.message.photo[-1].file_id
            media_type = "Photo"
        
        if file_id:
            await update.message.reply_text(f"{media_type} File ID:\n`{file_id}`")
    else:
        # If a non-admin sends media, the bot will do nothing.
        print(f"Ignoring media from non-admin user: {update.message.from_user.id}")
        return

def main() -> None:
    """Sets up and runs the bot."""
    print("Starting bot...")
    application = Application.builder().token(TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    
    # Register a single handler for both photos and videos
    application.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_media))

    # Start the Bot
    application.run_polling()
    print("Bot has stopped.")

if __name__ == '__main__':
    main()
