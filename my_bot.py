import os
import redis
import random
import string
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')
ADMIN_IDS = [789094994] 
ACCESS_DURATION = 24 * 60 * 60
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: DATA HELPERS (No changes here) ---
def get_media_catalog_keys():
    return db.smembers('catalog:keys')
def add_to_catalog(media_key, file_id):
    db.sadd('catalog:keys', media_key)
    db.set(f'media:{media_key}', file_id)
def get_random_media_file_id():
    random_key = db.srandmember('catalog:keys')
    if not random_key:
        return None
    return db.get(f'media:{random_key}')
def has_active_access(user_id):
    return db.exists(f'access:{user_id}')
def grant_user_access(user_id):
    db.set(f'access:{user_id}', 'active', ex=ACCESS_DURATION)
def create_unlock_token(user_id):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    db.set(f'unlock:{token}', user_id, ex=3600)
    return token
def validate_unlock_token(token):
    user_id = db.get(f'unlock:{token}')
    if user_id:
        db.delete(f'unlock:{token}')
        return int(user_id)
    return None

# --- SECTION 3: BOT FUNCTIONS ---

# The start function remains the same
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if context.args:
        payload = context.args[0]
        if payload.startswith("unlock-"):
            unlock_user_id = payload.split('-')[1]
            if str(user.id) == unlock_user_id:
                grant_user_access(user.id)
                keyboard = [[InlineKeyboardButton("🎬 Get Random Video", callback_data='get_video')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("✅ Access granted for 24 hours! Click the button below.", reply_markup=reply_markup)
            else:
                await update.message.reply_text("This is not your unlock link.")
            return
    if has_active_access(user.id):
        keyboard = [[InlineKeyboardButton("🎬 Get Random Video", callback_data='get_video')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Welcome back! You have an active pass.", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("🔓 Unlock for 24 Hours", callback_data='unlock_access')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Welcome! To watch videos, please unlock access.", reply_markup=reply_markup)

# The button_handler function remains the same
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == 'get_video':
        if has_active_access(user_id):
            file_id = get_random_media_file_id()
            if not file_id:
                await query.message.reply_text("Sorry, no media has been uploaded yet.")
                return
            keyboard = [[InlineKeyboardButton("🔄 Get Another Video", callback_data="get_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.reply_video(video=file_id, caption="Here's your random video!", protect_content=True, reply_markup=reply_markup)
            except:
                await query.message.reply_photo(photo=file_id, caption="Here's your random photo!", protect_content=True, reply_markup=reply_markup)
        else: # If they click "Get Video" but are locked, trigger the unlock flow
             await button_handler(update, context) # Re-route to the 'unlock_access' logic by calling the function again with a modified query
             query.data = 'unlock_access'
             await button_handler(update, context)

    elif query.data == 'unlock_access':
        bot_username = (await context.bot.get_me()).username
        unlock_link = f"https://t.me/{bot_username}?start={create_unlock_token(user_id)}"
        try:
            api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={unlock_link}&format=text"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    shortened_link = (await response.text()).strip()
            if not shortened_link:
                await query.message.reply_text("Sorry, an error occurred.")
                return
            keyboard = [[InlineKeyboardButton("👉 Watch Ad & Unlock 24h Access", url=shortened_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "👇 Click the link below and complete the ad to unlock videos for 24 hours:",
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.message.reply_text(f"Could not create an unlock link.")

# The admin media upload function remains the same
async def handle_admin_media_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (the admin media upload code remains exactly the same as before)
    if update.message.from_user.id not in ADMIN_IDS:
        await handle_text_messages(update, context) # If a non-admin sends media, treat it like a text message
        return
    file_id = None
    media_type = ""
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"
    if file_id:
        media_key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        add_to_catalog(media_key, file_id)
        catalog_count = db.scard('catalog:keys')
        await update.message.reply_text(
            f"✅ {media_type.title()} added! Total media: {catalog_count}"
        )

# --- NEW: Function to handle any text message ---
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles any text messages and guides users to use buttons."""
    if update.message.from_user.id in ADMIN_IDS:
        return  # Do nothing for admins, so they can type freely

    user_id = update.message.from_user.id
    
    # This logic is the same as the /start command, it shows the correct button
    if has_active_access(user_id):
        keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data="get_video")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Please use the button below to get videos:",
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("🔓 Unlock for 24 Hours", callback_data='unlock_access')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Please use the button below to unlock access:",
            reply_markup=reply_markup
        )

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_admin_media_upload))
    
    # NEW: Add handler for all non-command text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
