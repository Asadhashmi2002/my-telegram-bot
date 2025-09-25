import os
import redis
import random
import string
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- SECTION 1: CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
REDIS_URL = os.environ.get('REDIS_URL')
ADLINK_API_KEY = os.environ.get('ADLINK_API_KEY')

# Add your admin User IDs here
ADMIN_IDS = [789094994] 

# Connect to your Redis database
db = redis.from_url(REDIS_URL, decode_responses=True)

# --- SECTION 2: BOT FUNCTIONS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles deep links for both media and for unlocking 24-hour access."""
    if context.args:
        payload = context.args[0]
        user_id = update.message.from_user.id

        # Check if this is an unlock link
        if payload.startswith("unlock-"):
            unlock_user_id = payload.split('-')[1]
            if str(user_id) == unlock_user_id:
                # Grant user 24-hour access by setting a key with an expiration
                # 86400 seconds = 24 hours
                db.set(f"user:{user_id}", "active", ex=86400)
                await update.message.reply_text("✅ Access granted for 24 hours! You can now use the /video command.")
            else:
                await update.message.reply_text("This is not your unlock link.")
            return

        # Original logic for direct media links
        file_id = db.get(payload)
        if file_id:
            try:
                await update.message.reply_video(video=file_id, caption="Here is your media!", protect_content=True)
            except Exception:
                await update.message.reply_photo(photo=file_id, caption="Here is your media!", protect_content=True)
        else:
            await update.message.reply_text("Sorry, I don't recognize that link code.")
    else:
        await update.message.reply_text("Hello! Use /video to get a random video.")

async def get_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /video command for regular users."""
    user_id = update.message.from_user.id

    # Check if the user has an active pass in the database
    if db.exists(f"user:{user_id}"):
        # User has access, send a random video
        all_video_keys = db.smembers("all_media_keys")
        if not all_video_keys:
            await update.message.reply_text("Sorry, no videos have been uploaded by the admin yet.")
            return

        random_key = random.choice(list(all_video_keys))
        file_id = db.get(random_key)

        if file_id:
             try:
                await update.message.reply_video(video=file_id, caption="Here's your random video!", protect_content=True)
             except:
                await update.message.reply_photo(photo=file_id, caption="Here's your random photo!", protect_content=True)
    else:
        # User does not have access, send them the monetized unlock link
        bot_username = (await context.bot.get_me()).username
        unlock_link = f"https://t.me/{bot_username}?start=unlock-{user_id}"
        
        try:
            api_url = f"https://inshorturl.com/api?api={ADLINK_API_KEY}&url={unlock_link}&format=text"
            response = requests.get(api_url)
            shortened_link = response.text.strip()
            
            if not shortened_link:
                await update.message.reply_text("Sorry, there was an error creating an unlock link. Please try again later.")
                return

            await update.message.reply_text(
                "Your access has expired.\n\n"
                f"Click the link below and complete the ad to unlock unlimited videos for 24 hours:\n{shortened_link}"
            )
        except Exception as e:
            print(f"Error creating unlock link: {e}")
            await update.message.reply_text("Could not create an unlock link at this time.")

async def add_media_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves a file_id and its code to the database. Admin only."""
    if update.message.from_user.id not in ADMIN_IDS:
        return

    try:
        replied_message = update.message.reply_to_message
        if not replied_message or (not replied_message.photo and not replied_message.video):
            await update.message.reply_text("Please reply to a photo or video to use this command.")
            return

        file_id = replied_message.photo[-1].file_id if replied_message.photo else replied_message.video.file_id
        link_code = context.args[0]
        
        # Save the link code and file_id
        db.set(link_code, file_id)
        # Also add the link code to a master list for random selection
        db.sadd("all_media_keys", link_code)
        
        bot_username = (await context.bot.get_me()).username
        final_link = f"https://t.me/{bot_username}?start={link_code}"

        await update.message.reply_text(f"✅ Direct link created for '{link_code}'!\n\nThis link will bypass the 24-hour ad-wall:\n{final_link}")

    except (IndexError, TypeError):
        await update.message.reply_text("Usage: Reply to a photo/video and use the command `/add <unique_link_code>`")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

def main() -> None:
    """Sets up and runs the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("video", get_video_command))
    application.add_handler(CommandHandler("add", add_media_command)) # Admin command

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
