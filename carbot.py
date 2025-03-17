
import logging
import os
import asyncio
from telethon import TelegramClient, events
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CallbackContext, MessageHandler, filters
from telegram.request import HTTPXRequest
from httpx import AsyncClient, Limits
import nest_asyncio

# ✅ Apply async fix for Jupyter Notebooks (if applicable)
nest_asyncio.apply()

# ✅ Configure Logging
logging.basicConfig(filename="carbot.log", level=logging.INFO, format="%(asctime)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

logging.info("🚀 Bot is starting...")

# ✅ Telegram Credentials
BOT_A_TOKEN = "8128768740:AAGhjPxoSR1lkMK7JbLkW25jNmuVJ_8ANbU"
BOT_B_USERNAME = "expressfaxbot"

# ✅ Telegram User API Credentials (for forwarding)
API_ID = 20842249
API_HASH = "855577623bf2304a2c19be8b1a695c1a"
PHONE = "+18624146897"
ADMIN_TELEGRAM_ID = 299027877

# ✅ Allowed Users
ALLOWED_TELEGRAM_IDS = {299027877,5468665903}  

# ✅ Fix session file path
SESSION_FILE = "./session.session"

# ✅ HTTPX request with connection pooling (for improved performance)
transport = AsyncClient(
    timeout=60,  
    limits=Limits(max_connections=1000, max_keepalive_connections=500)
)
bot_request = HTTPXRequest()

# ✅ Initialize Bot A
bot_a = Bot(token=BOT_A_TOKEN, request=bot_request)
app = ApplicationBuilder().token(BOT_A_TOKEN).request(bot_request).build()

# ✅ Initialize Telethon user client
user_client = TelegramClient(SESSION_FILE, API_ID, API_HASH, connection_retries=10, timeout=30)

# ✅ Store user-message mappings
user_sessions = {}  # Maps Bot B's chat ID to the original user ID
processed_messages = set()  # Prevent duplicate processing

# ✅ Directory to Save Images
IMAGE_DIR = "received_images"
os.makedirs(IMAGE_DIR, exist_ok=True)  # Ensure directory exists


# 🔹 **Step 1: Forward Messages & Access Control**
async def forward_to_bot_b(update: Update, context: CallbackContext):
    """Handles messages received by Bot A and forwards only specific messages to the admin."""
    user_id = update.message.chat_id
    user_message = update.message.text.lower()  # Convert to lowercase for case-insensitive matching
    user_name = update.message.from_user.username or "Unknown"
    full_name = update.message.from_user.full_name or "Unknown"

    logging.info(f"📩 Bot A received from {user_name} ({full_name}) [ID: {user_id}]: {update.message.text}")

    # ✅ Forward specific messages to Admin
    if "my name is" in user_message or "my telegram id is" in user_message:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID,
                text=f"📩 New verified message from {user_name} ({full_name}):\n\n{update.message.text}"
            )
            logging.info(f"✅ Forwarded to Admin: {update.message.text}")
        except Exception as e:
            logging.error(f"❌ Failed to forward message to Admin: {e}")
            
    # ✅ Check if the user is allowed
    if user_id not in ALLOWED_TELEGRAM_IDS:
        await update.message.reply_text(
            "❌ Access Denied!\n\n"
            "To gain access, please complete the $30 payment and follow the instructions below:\n\n"
            "💰 Payment Link: https://buy.stripe.com/5kA8ACfSr8XxeIM288\n\n"
            "After Payment:\n"
            "‼️ Send a message in this EXACT FORMAT:\n\n"
            "    My payment name is [Your Name] and my Telegram ID is [Your ID]\n\n"
            "⚠️ Important:\n"
            "- Your Telegram ID must be NUMBERS ONLY.\n"
            "- To find your Telegram ID, message @userinfobot in Telegram.\n"
            "- Incorrect formats will be ignored.\n\n"
            "📞 If you need help, contact support at carfaxgod@mail.com."
        )
        logging.warning(f"🚫 Unauthorized access attempt by {user_name} ({full_name}) [ID: {user_id}].")
        return  # ✅ Ensure early return to stop further processing

    # ✅ Forward message to Bot B via the user client (Only Once)
    try:
        sent_message = await user_client.send_message(BOT_B_USERNAME, update.message.text)
        user_sessions[sent_message.chat_id] = user_id  # Store chat_id mapping
        logging.info(f"✅ Forwarded to Bot B: {update.message.text}")
    except Exception as e:
        logging.error(f"❌ Failed to forward message to Bot B: {e}")


# 🔹 **Step 2: Handle Replies from Bot B**
@user_client.on(events.NewMessage(from_users=BOT_B_USERNAME))
async def handle_reply_from_bot_b(event):
    """Handles responses from Bot B and forwards ONLY documents or 'This is not a valid VIN' messages to Bot A."""
    logging.info(f"🔄 Bot B replied: {event.raw_text or 'Non-text message'}")

    if event.id in processed_messages:
        logging.warning("⚠️ Duplicate message detected, skipping.")
        return
    processed_messages.add(event.id)

    user_id = user_sessions.get(event.chat_id)
    if not user_id:
        logging.warning("⚠️ No matching user session found for this message. Skipping.")
        return

    # ✅ Forward ONLY "This is not a valid VIN" message
    if event.text and event.text.strip().lower() in ["this is not a valid vin", "el vin no es válido"]:
        try:
            await bot_a.send_message(chat_id=user_id, text=event.text)
            logging.info(f"📩 Sent VIN error message to user {user_id}")
        except Exception as e:
            logging.error(f"❌ Failed to forward VIN message to {user_id}: {e}")


    # ✅ Forward ONLY document messages from Bot B to Bot A
    elif hasattr(event.media, "document"):
        media_file = await event.download_media()
        with open(media_file, "rb") as file:
            try:
                await bot_a.send_document(chat_id=user_id, document=file)
                logging.info(f"📄 Document forwarded to user {user_id}")
            except Exception as e:
                logging.error(f"❌ Failed to forward document to {user_id}: {e}")

    else:
        logging.warning(f"⚠️ Unrecognized response from Bot B. Ignoring.")



# 🔹 **Step 3: Start the Bot**
async def run():
    """Runs both Bot A (Polling) and the Telethon user client concurrently."""
    if os.path.exists(SESSION_FILE):
        os.chmod(SESSION_FILE, 0o600)  

    await user_client.start(PHONE)
    logging.info("✅ User client logged in!")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_bot_b))
    await asyncio.gather(
        user_client.run_until_disconnected(),
        app.run_polling()
    )


# ✅ **Start the Bot**
if __name__ == "__main__":
    asyncio.run(run())
