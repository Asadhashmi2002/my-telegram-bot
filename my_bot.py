import os
import redis
import random
import string
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- SECTION 1: CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')
ADMIN_IDS = [789094994] 
ACCESS_DURATION = 24 * 60 * 60
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: HELPER FUNCTIONS ---
def has_active_access(user_id):
    """Checks if a user's access key exists in Redis."""
    return db.exists(f'access:{user_id}')

def get_random_media_file_id():
    """Gets a random media key from the catalog set and returns its file_id."""
    random_key = db.srandmember('catalog:keys')
    if not random_key:
        return None
    return db.get(f'media:{random_key}')

# --- SECTION 3: CORE BOT LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command, deep links, and shows the correct initial buttons."""
    user = update.effective_user
    
    # Check if the /start command has a deep link payload
    if context.args:
        payload = context.args[0]
        # Check if the payload is a valid unlock token from our database
        token_user_id = db.get(f"unlock:{payload}")
        if token_user_id and int(token_user_id) == user.id:
            db.delete(f"unlock:{payload}") # Consume the token so it can't be reused
            db.set(f"access:{user.id}", "active", ex=ACCESS_DURATION) # Grant access
            
            # After unlocking, show the "Get Video" button
            keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data='get_video')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("✅ Access granted for 24 hours! Click the button below to start.", reply_markup=reply_markup)
            return

    # If no valid deep link, show buttons based on current access status
    if has_active_access(user.id):
        keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data='get_video')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Welcome back! You have an active pass. Click to get a video.", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("🔓 Unlock for 24 Hours", callback_data='unlock_access')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Welcome! To watch videos, please unlock access.", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all button clicks from users."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    # If user clicks "Get Video"
    if query.data == 'get_video':
        if has_active_access(user.id):
            file_id = get_random_media_file_id()
            if not file_id:
                await query.message.reply_text("Sorry, no media has been uploaded by the admin yet.")
                return
            
            keyboard = [[InlineKeyboardButton("🔄 Get Another Video", callback_data="get_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # We use query.bot.send_video instead of reply_video to avoid issues
                await query.bot.send_video(chat_id=user.id, video=file_id, caption="Here's your random video!", protect_content=True, reply_markup=reply_markup)
            except Exception:
                await query.bot.send_photo(chat_id=user.id, photo=file_id, caption="Here's your random photo!", protect_content=True, reply_markup=reply_markup)
        else:
            # If a locked user somehow clicks "Get Video", send them the unlock link
            await send_unlock_link(query.message, context, user)

    # If user clicks "Unlock Access"
    elif query.data == 'unlock_access':
        await send_unlock_link(query.message, context, user)

async def send_unlock_link(message, context, user):
    """Helper function to create and send the monetized unlock link."""
    bot_username = (await context.bot.get_me()).username
    
    # Create a unique, temporary token for the unlock link, valid for 1 hour
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    db.set(f"unlock:{token}", user.id, ex=3600) 
    
    unlock_link = f"https://t.me/{bot_username}?start={token}"

    try:
        api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={unlock_link}&format=text"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                shortened_link = (await response.text()).strip()
        
        if not shortened_link:
            await message.reply_text("Sorry, there was an error creating the link. Please try again.")
            return
            
        keyboard = [[InlineKeyboardButton("👉 Watch Ad & Unlock 24h Access", url=shortened_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "👇 Click the button and complete the ad to unlock videos for 24 hours.",
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error creating unlock link: {e}")
        await message.reply_text("Could not create an unlock link at this time.")

async def admin_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles media uploads from admins to add to the catalog."""
    if update.message.from_user.id not in ADMIN_IDS:
        await text_handler(update, context) # If non-admin sends media, treat as text
        return

    file_id = None
    media_type = ""
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "Photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "Video"

    if file_id:
        media_key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        db.set(f"media:{media_key}", file_id)
        db.sadd('catalog:keys', media_key)
        
        catalog_count = db.scard('catalog:keys')
        await update.message.reply_text(f"✅ {media_type} added! Total media: {catalog_count}")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any text from non-admins and guides them to use /start."""
    if update.message.from_user.id in ADMIN_IDS:
        return # Admins can type freely

    # For regular users, just prompt them to use the start command to see the buttons
    await update.message.reply_text("Please use the /start command to begin.")

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, admin_upload_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
