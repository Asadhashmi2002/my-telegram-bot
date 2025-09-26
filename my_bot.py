import os
import redis
import random
import string
import time
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION ---

# Gets secrets from Railway's "Variables" tab
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')

# Validate required secrets at startup
if not TOKEN:
    raise ValueError("TOKEN environment variable is required")
if not ADLINK_API_KEY:
    raise ValueError("ADLINK_API_KEY environment variable is required")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is required")

print("✅ All required secrets are configured")

# Add your admin User IDs here
ADMIN_IDS = [789094994]

# Access duration in seconds (24 hours)
ACCESS_DURATION = 24 * 60 * 60

# Connect to your Redis database
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: DATA HELPERS (Rewritten for Redis) ---

def get_media_catalog_keys():
    """Get list of all uploaded media keys from a Redis Set."""
    return db.smembers('catalog:keys')

def add_to_catalog(media_key, file_id):
    """Add media to catalog using a Redis Set and a Hash."""
    db.sadd('catalog:keys', media_key) # Add the key to our set of all keys
    db.set(f'media:{media_key}', file_id) # Store the file_id

def get_random_media_file_id():
    """Get random media file_id from catalog using Redis SRANDMEMBER."""
    random_key = db.srandmember('catalog:keys')
    if not random_key:
        return None
    return db.get(f'media:{random_key}')

def has_active_access(user_id):
    """Check if a user has an active access key in Redis."""
    return db.exists(f'access:{user_id}')

def grant_user_access(user_id):
    """Grant user access by setting a key in Redis with a 24-hour expiration."""
    db.set(f'access:{user_id}', 'active', ex=ACCESS_DURATION)

def create_unlock_token(user_id):
    """Create a temporary unlock token in Redis with a 1-hour expiration."""
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    db.set(f'unlock:{token}', user_id, ex=3600) # Token expires in 1 hour
    return token

def validate_unlock_token(token):
    """Validate and consume unlock token from Redis."""
    user_id = db.get(f'unlock:{token}')
    if user_id:
        db.delete(f'unlock:{token}') # Consume token
        return int(user_id)
    return None

# --- SECTION 3: BOT FUNCTIONS (Now using Redis helpers) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    if context.args:
        # Handle unlock tokens
        token = context.args[0]
        unlocked_user_id = validate_unlock_token(token)
        
        if unlocked_user_id and unlocked_user_id == user_id:
            grant_user_access(user_id)
            hours = ACCESS_DURATION // 3600
            keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data="get_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🎉 Success! You now have {hours} hours of unlimited video access!",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Invalid or expired unlock link.")
    else:
        # Check access and show appropriate buttons
        if has_active_access(user_id):
            keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data="get_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎬 Welcome back! You have unlimited video access.",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("🎬 Get Video", callback_data="get_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎬 Welcome to Video Bot!\nClick the button below to start watching videos.",
                reply_markup=reply_markup
            )

async def handle_get_video_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if has_active_access(user_id):
        file_id = get_random_media_file_id()
        if not file_id:
            await query.message.reply_text("📹 No videos available yet. Please check back later!")
            return
            
        keyboard = [[InlineKeyboardButton("🔄 Get Another Video", callback_data="get_video")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.reply_video(video=file_id, caption="🎬 Enjoy your video!", protect_content=True, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_photo(photo=file_id, caption="📸 Enjoy your media!", protect_content=True, reply_markup=reply_markup)
    else:
        # Create unlock link
        token = create_unlock_token(user_id)
        bot_username = (await context.bot.get_me()).username
        unlock_link = f"https://t.me/{bot_username}?start={token}"
        
        try:
            api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={unlock_link}&format=text"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    monetized_link = (await response.text()).strip()
            
            if not monetized_link:
                await query.message.reply_text("❌ Error creating unlock link. Please try again.")
                return
                
            keyboard = [[InlineKeyboardButton("👉 Watch Ad & Unlock 24h Access", url=monetized_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "🔒 To unlock 24 hours of unlimited videos, click the button below to watch a quick ad.",
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")

async def handle_admin_media_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle media uploads from admins"""
    if update.message.from_user.id not in ADMIN_IDS:
        return # Silently ignore media from non-admins

    file_id = None
    media_type = ""
    
    if update.message.photo:
        file_id = update.message.photo[--1].file_id
        media_type = "photo"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"

    if file_id:
        media_key = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        add_to_catalog(media_key, file_id)
        
        catalog_count = db.scard('catalog:keys')
        await update.message.reply_text(
            f"✅ {media_type.title()} added to catalog!\n"
            f"📊 Total media in catalog: {catalog_count}"
        )

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_get_video_button, pattern="get_video"))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_admin_media_upload))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
