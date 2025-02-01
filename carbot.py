import logging

# ✅ Configure logging to write to bot.log and show logs in console
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ✅ Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

logging.info("🚀 Bot is starting...")

import asyncio
from telethon.errors import FloodWaitError
from asyncio.exceptions import TimeoutError
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CallbackContext, MessageHandler, filters
import httpx
import os
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument
from telegram import Update, Bot
from telegram.request import HTTPXRequest

# ✅ Telegram User API Credentials (for forwarding messages)
API_ID = "20842249"
API_HASH = "855577623bf2304a2c19be8b1a695c1a"
PHONE = "+18624146897"  # This must be a real Telegram user account

# ✅ Telegram Bot A credentials
BOT_A_TOKEN = "8128768740:AAGhjPxoSR1lkMK7JbLkW25jNmuVJ_8ANbU"

# ✅ Bot B username (the existing bot you don’t control)
BOT_B_USERNAME = "expressfaxbot"

# ✅ Store user-message mappings
user_sessions = {}  # Maps Bot B's chat ID to the original user ID
processed_messages = set()  # Prevent duplicate processing

# ✅ List of Allowed Telegram User IDs
ALLOWED_TELEGRAM_IDS = {1856500551,299027877,470715774}  # Replace with actual allowed IDs

# ✅ Ensure session file is stored in a writable directory
SESSION_FILE = "/tmp/session.session"  # Change to a writable location

# ✅ Initialize Telethon client for the user account
SESSION_FILE = "./session.session"  # Store in current directory instead of /tmp
user_client = TelegramClient(SESSION_FILE, API_ID, API_HASH, connection_retries=10, timeout=30)

from httpx import AsyncClient
from telegram.request import HTTPXRequest

# ✅ Corrected HTTPX transport with connection pooling
from httpx import AsyncClient, Limits

# ✅ Corrected HTTPX transport with Limits object
transport = AsyncClient(
    timeout=60,  # Global timeout
    limits=Limits(max_connections=1000, max_keepalive_connections=500)  # ✅ Corrected format
)

bot_request = HTTPXRequest()

# ✅ Initialize Bot A with the new HTTPX request settings
bot_a = Bot(token=BOT_A_TOKEN, request=bot_request)
app = ApplicationBuilder().token(BOT_A_TOKEN).request(bot_request).build()

async def send_with_retry(send_function, *args, **kwargs):
    """Retries sending a Telegram message if a timeout occurs."""
    for attempt in range(6):  # Retry up to 3 times
        try:
            return await send_function(*args, **kwargs)  # Increase timeout to 60s
        except asyncio.TimeoutError:
            print(f"⚠️ Timeout occurred. Retrying ({attempt + 1}/6)...")
            await asyncio.sleep(2)  # Wait 2 seconds before retrying
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break
    print("❌ Failed to send after 6 attempts.")

# ✅ Step 1: Receive Messages in Bot A and Forward to Bot B
async def forward_to_bot_b(update: Update, context: CallbackContext):
    """Handles messages received by Bot A and forwards them to Bot B via the user account."""
    user_id = update.message.chat_id  # Store original user ID
    user_message = update.message.text

    # 🔍 Debug: Print raw update
    print(f"📩 Raw Update Received: {update}")

    if not user_message:
        print("⚠️ No text message detected, skipping.")
        return  # Skip non-text messages

   # ✅ Check if the user is in the allowed list
    if user_id not in ALLOWED_TELEGRAM_IDS:
        await update.message.reply_text("❌ Access Denied. Please send your $30 monthly payment to zelle: carfaxgod@mail.com." then send the payment screenshot to get access.)
        print(f"🚫 Unauthorized access attempt by {user_id}.")
        return  # Stop processing further
    user_message = update.message.text
    print(f"📩 Bot A received from {user_id}: {user_message}")

    # ✅ Forward message to Bot B using Telethon
    try:
        sent_message = await user_client.send_message(BOT_B_USERNAME, user_message)
        user_sessions[sent_message.chat_id] = user_id  # ✅ Store chat_id mapping
        print(f"✅ Forwarded to Bot B: {user_message}")
    except Exception as e:
        print(f"❌ Failed to forward message to Bot B: {e}")

@user_client.on(events.NewMessage(from_users=BOT_B_USERNAME))
async def handle_reply_from_bot_b(event):
    """Handles responses from Bot B and forwards valid messages to Bot A."""
    print(f"🔄 Bot B replied: {event.raw_text or 'Non-text message'}")

    # Avoid duplicate processing
    if event.id in processed_messages:
        print("⚠️ Duplicate message detected, skipping.")
        return
    processed_messages.add(event.id)

    user_id = user_sessions.get(event.chat_id)
    if not user_id:
        print("⚠️ No matching user session found for this message. Skipping.")
        return

    # ✅ Forward ONLY "This is not a valid VIN" message
    if event.text and event.text.strip().lower() == "this is not a valid vin":
        await send_with_retry(bot_a.send_message, chat_id=user_id, text=event.text)

    # ✅ Forward ONLY Document Messages
    elif hasattr(event.media, "document"):  # Checks if it contains a document
        media_file = await event.download_media()
        with open(media_file, "rb") as file:
            await send_with_retry(bot_a.send_document, chat_id=user_id, document=file)

    else:
        print(f"⚠️ Unrecognized response from Bot B: '{event.text}'. Skipping.")

# ✅ STEP 3: Start Everything Fresh
async def run():
    """Runs both Bot A and the Telethon user client concurrently."""

    # ✅ Fix session file permissions before starting
    if os.path.exists(SESSION_FILE):
        os.chmod(SESSION_FILE, 0o600)  # Ensure the file is readable & writable by the user

    await user_client.start(PHONE)  # Ensure the user client logs in
    print("✅ User client logged in!")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_bot_b))

    await asyncio.gather(
        user_client.run_until_disconnected(),
        app.run_polling()
    )

# ✅ Restart Bot Cleanly
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()  # ✅ Apply fix for Jupyter event loop
    asyncio.run(run())
