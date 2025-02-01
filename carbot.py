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

# ✅ Allowed Users
ALLOWED_TELEGRAM_IDS = {299027877, 470715774}  # Replace with actual user IDs

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


# 🔹 **Step 1: Handle Incoming Messages in Bot A**
async def forward_to_bot_b(update: Update, context: CallbackContext):
    """Handles messages received by Bot A and forwards them to Bot B."""
    user_id = update.message.chat_id
    user_message = update.message.text

    logging.info(f"📩 Bot A received from {user_id}: {user_message}")

    if not user_message:
        logging.warning("⚠️ No text message detected, skipping.")
        return

    # ✅ Check if the user is allowed
    if user_id not in ALLOWED_TELEGRAM_IDS:
        await update.message.reply_text(
            "❌ *Access Denied!*\n\n"
            "To gain access, please complete the $30 payment and follow the instructions below:\n\n"
            "💰 *Payment Link:* https://buy.stripe.com/5kA8ACfSr8XxeIM288)\n\n"
            "📸 *After Payment:*\n"
            "1️⃣ Send a message in *this exact format*:\n\n"
            "   *My payment name is [Your Name] and my Telegram ID is [Your ID]*\n\n"
            "⚠️ *Important:*\n"
            "- Your Telegram ID must be *numbers only*.\n"
            "- To find your Telegram ID, message *@userinfobot* in Telegram.\n"
            "- *Incorrect formats will be ignored.*\n\n"
            "📞 If you need help, contact support carfaxgod@mail.com."
        )
        logging.warning(f"🚫 Unauthorized access attempt by user {user_id}.")
        return

    # ✅ Forward message to Bot B via the user client
    try:
        sent_message = await user_client.send_message(BOT_B_USERNAME, user_message)
        user_sessions[sent_message.chat_id] = user_id  # Store chat_id mapping
        logging.info(f"✅ Forwarded to Bot B: {user_message}")
    except Exception as e:
        logging.error(f"❌ Failed to forward message to Bot B: {e}")


    # ✅ Forward message to Bot B via the user client
    try:
        sent_message = await user_client.send_message(BOT_B_USERNAME, user_message)
        user_sessions[sent_message.chat_id] = user_id  # Store chat_id mapping
        logging.info(f"✅ Forwarded to Bot B: {user_message}")
    except Exception as e:
        logging.error(f"❌ Failed to forward message to Bot B: {e}")


# 🔹 **Step 2: Handle Replies from Bot B**
@user_client.on(events.NewMessage(from_users=BOT_B_USERNAME))
async def handle_reply_from_bot_b(event):
    """Handles responses from Bot B and forwards valid messages to Bot A."""
    logging.info(f"🔄 Bot B replied: {event.raw_text or 'Non-text message'}")

    if event.id in processed_messages:
        logging.warning("⚠️ Duplicate message detected, skipping.")
        return
    processed_messages.add(event.id)

    user_id = user_sessions.get(event.chat_id)
    if not user_id:
        logging.warning("⚠️ No matching user session found for this message. Skipping.")
        return

    # ✅ Forward only "This is not a valid VIN" message
    if event.text and event.text.strip().lower() == "this is not a valid vin":
        await bot_a.send_message(chat_id=user_id, text=event.text)

    # ✅ Forward only document messages
    elif hasattr(event.media, "document"):
        media_file = await event.download_media()
        with open(media_file, "rb") as file:
            await bot_a.send_document(chat_id=user_id, document=file)

    else:
        logging.warning(f"⚠️ Unrecognized response from Bot B: '{event.text}'. Skipping.")


# 🔹 **Step 3: Receive & Log Photos (Without Replying)**
async def receive_photo(update: Update, context: CallbackContext):
    """Receives photos from users and logs them without replying."""
    user_id = update.message.chat_id

    if update.message.photo:
        photo = update.message.photo[-1]  # Get the highest resolution photo
        file_id = photo.file_id
        file = await context.bot.get_file(file_id)  # Get the file object

        # ✅ Save the image locally
        file_path = os.path.join(IMAGE_DIR, f"{user_id}_{file_id}.jpg")
        await file.download_to_drive(file_path)

        # ✅ Log the image receipt (Show in Backend)
        logging.info(f"📷 Image received from {user_id}: Saved as {file_path}")

    else:
        logging.warning(f"⚠️ User {user_id} sent a non-photo message. Ignoring.")


# 🔹 **Step 4: Start Everything Together**
async def run():
    """Runs both Bot A (Polling) and the Telethon user client concurrently."""
    
    # ✅ Fix session file permissions before starting
    if os.path.exists(SESSION_FILE):
        os.chmod(SESSION_FILE, 0o600)  

    await user_client.start(PHONE)  # Ensure the user client logs in
    logging.info("✅ User client logged in!")

    # ✅ Add Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_bot_b))
    app.add_handler(MessageHandler(filters.PHOTO, receive_photo))  # <=== Added for photos

    await asyncio.gather(
        user_client.run_until_disconnected(),
        app.run_polling()
    )


# ✅ **Start the Bot**
if __name__ == "__main__":
    asyncio.run(run())
