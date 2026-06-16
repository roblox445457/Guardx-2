import os
import logging
import sys
import threading
import time
from flask import Flask
from bot import DiscordBot
import discord
import discord.errors

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Antiguard Bot is running", 200

def run_flask():
    try:
        app.run(host="0.0.0.0", port=5000)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error("Port 5000 is already in use! Please make sure no other processes are using this port.")
            sys.exit(1)
        else:
            logger.error(f"Failed to start Flask server: {str(e)}")
            sys.exit(1)

# Initialize and run bot
if __name__ == '__main__':
    try:
        logger.info("Starting Flask web server...")
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True  # Make thread daemon so it exits when main thread exits
        flask_thread.start()

        logger.info("Starting bot initialization...")

        # Check for token
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN not found in environment variables!")
            sys.exit(1)

        # Add retries for Discord connection
        max_retries = 5
        retry_delay = 5  # in seconds

        for attempt in range(1, max_retries + 1):
            try:
                # Create a fresh bot instance for each attempt
                logger.info(f"Creating bot instance (attempt {attempt}/{max_retries})...")
                bot = DiscordBot()
                
                logger.info(f"Starting bot (attempt {attempt}/{max_retries})...")
                bot.run(token)
                break  # If successful, break out of the retry loop
            except (discord.errors.HTTPException, RuntimeError) as e:
                if attempt < max_retries:  # We have more retries available
                    wait_time = retry_delay * attempt  # Exponential backoff
                    if isinstance(e, discord.errors.HTTPException) and e.status == 429:
                        logger.warning(f"Hit Discord rate limit. Waiting {wait_time} seconds before retry...")
                    else:
                        logger.warning(f"Discord connection error: {str(e)}. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    # If we've exhausted our retries
                    logger.error(f"Discord API error after {max_retries} attempts: {str(e)}")
                    sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        sys.exit(1)