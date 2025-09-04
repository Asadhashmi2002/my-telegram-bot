from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
# --- THIS IS THE LINE YOU MUST EDIT ---
# Replace the text inside the quotes with your actual bot token.
#token removed


TOKEN = os.environ['TOKEN']
# -------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command and deep linking."""
    
    # Check if the /start command has a payload
    if context.args:
        payload = context.args[0]
        
        # Logic for the first payload (video)
        if payload == "send_big_buck_bunny":
            video_url = 'https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-mp4-file.mp4'
            await update.message.reply_video(video=video_url, caption='Here is your special video!')
            
        # Logic for the second payload (photo)
        elif payload == "send_a_cool_photo":
            photo_url = 'https://picsum.photos/seed/picsum/800' 
            await update.message.reply_photo(photo=photo_url, caption='Here is a cool photo!')

        # Logic for any other unrecognized payload
        else:
            await update.message.reply_text(f"I don't recognize the code: {payload}")
            
    # This runs if the user just sends a normal /start command without a payload
    else:
        await update.message.reply_text(
            'Hello! I am your bot.\n'
            'You can use special links to get content directly from me.'
        )

def main() -> None:
    """Sets up and runs the bot."""
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # Register the /start command handler
    application.add_handler(CommandHandler("start", start))

    # Start the Bot and print a message to the console
    print("Bot is running... Press Ctrl+C to stop.")
    
    # Run the bot until the user presses Ctrl+C
    application.run_polling()

# This part makes the script runnable
if __name__ == '__main__':
    main()
