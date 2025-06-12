import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import sqlite3
from datetime import datetime
from enum import Enum
import os

# --- Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Recommended to use environment variables
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_NAME = "appeals.db"

# --- Enums ---
class AppealType(Enum):
    UNBAN = "unban"
    ADMIN = "admin"

class AppealStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# --- Database Utilities ---
class DB:
    @staticmethod
    def get_connection():
        return sqlite3.connect(DATABASE_NAME)

    @staticmethod
    def execute(query: str, params=(), commit: bool = False):
        with DB.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if commit:
                conn.commit()
            return cursor

# --- Database Setup ---
def init_db():
    DB.execute('''CREATE TABLE IF NOT EXISTS appeals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 username TEXT NOT NULL,
                 appeal_type TEXT NOT NULL,
                 status TEXT DEFAULT "pending" CHECK(status IN ('pending', 'approved', 'rejected')),
                 timestamp TEXT NOT NULL)''',
              commit=True)

init_db()

# --- Decorators ---
def admin_only(func):
    """Restrict command access to admin only"""
    def wrapper(update: Update, context: CallbackContext):
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("⛔ Unauthorized access!")
            return
        return func(update, context)
    return wrapper

# --- User Commands ---
def start(update: Update, context: CallbackContext):
    """Send welcome message with basic instructions"""
    update.message.reply_text(
        "📝 Use /appeal to submit a FedBan appeal or request Fed Admin status"
    )

def appeal(update: Update, context: CallbackContext):
    """Show appeal type selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔓 Fed Unban Appeal", callback_data=AppealType.UNBAN.value)],
        [InlineKeyboardButton("👑 Fed Admin Request", callback_data=AppealType.ADMIN.value)]
    ]
    update.message.reply_text(
        "Select appeal type:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def handle_appeal(update: Update, context: CallbackContext):
    """Handle appeal type selection from inline keyboard"""
    query = update.callback_query
    user = query.from_user

    try:
        # Validate appeal type
        appeal_type = AppealType(query.data)
        
        # Save to database
        DB.execute(
            '''INSERT INTO appeals 
            (user_id, username, appeal_type, timestamp)
            VALUES (?, ?, ?, ?)''',
            (user.id, user.username, appeal_type.value, datetime.now().isoformat()),
            commit=True
        )
        
        query.edit_message_text(f"✅ {appeal_type.value.capitalize()} appeal submitted!")
        
        # Notify admin
        context.bot.send_message(
            ADMIN_ID,
            f"🚨 New Appeal\n"
            f"User: @{user.username}\n"
            f"Type: {appeal_type.value}\n"
            f"Time: {datetime.now().strftime('%H:%M %d-%m-%Y')}\n\n"
            "Use /pending to view all appeals"
        )
    except ValueError as e:
        logger.error(f"Invalid appeal type: {e}")
        query.edit_message_text("❌ Invalid appeal type selected!")

# --- Admin Commands ---
@admin_only
def pending(update: Update, context: CallbackContext):
    """Show all pending appeals with pagination"""
    page = int(context.args[0]) if context.args else 0
    limit = 5  # Items per page
    
    with DB.get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM appeals WHERE status=?", (AppealStatus.PENDING.value,))
        total = c.fetchone()[0]
        c.execute("SELECT * FROM appeals WHERE status=? LIMIT ? OFFSET ?", 
                 (AppealStatus.PENDING.value, limit, page * limit))
        appeals = c.fetchall()

    if not appeals:
        update.message.reply_text("No pending appeals!")
        return

    response = [f"📋 Pending Appeals (Page {page+1}):\n"]
    for appeal in appeals:
        response.append(
            f"\nID: {appeal[0]}\n"
            f"User: @{appeal[2]} (ID: {appeal[1]})\n"
            f"Type: {appeal[3]}\n"
            f"Time: {appeal[5]}\n"
            "───────────────"
        )

    keyboard = []
    if page > 0:
        keyboard.append(InlineKeyboardButton("⬅ Previous", callback_data=f"page_{page-1}"))
    if (page + 1) * limit < total:
        keyboard.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))
    
    update.message.reply_text(
        "\n".join(response),
        reply_markup=InlineKeyboardMarkup([keyboard]) if keyboard else None
    )

@admin_only
def resolve_appeal(update: Update, context: CallbackContext, status: AppealStatus):
    """Generic function to handle appeal resolution"""
    try:
        appeal_id = context.args[0]
        if not appeal_id.isdigit():
            raise ValueError("Invalid appeal ID")
            
        with DB.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE appeals SET status=? WHERE id=?", (status.value, appeal_id))
            
            if c.rowcount == 0:
                update.message.reply_text("⚠ Appeal ID not found!")
                return
                
            c.execute("SELECT user_id FROM appeals WHERE id=?", (appeal_id,))
            user_id = c.fetchone()[0]
            conn.commit()

        update.message.reply_text(f"{status.value.capitalize()} appeal #{appeal_id}")
        context.bot.send_message(
            user_id, 
            f"📨 Your appeal has been {status.value}!\n\n"
            f"Reference ID: {appeal_id}"
        )
    except (IndexError, ValueError) as e:
        logger.error(f"Error in resolve_appeal: {e}")
        update.message.reply_text(f"Usage: /{status.value} <appeal_id>")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        update.message.reply_text("❌ Error processing request")

# --- Bot Setup ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # User commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("appeal", appeal))
    
    # Admin commands
    dp.add_handler(CommandHandler("pending", pending))
    dp.add_handler(CommandHandler("approve", lambda u, c: resolve_appeal(u, c, AppealStatus.APPROVED)))
    dp.add_handler(CommandHandler("reject", lambda u, c: resolve_appeal(u, c, AppealStatus.REJECTED)))
    
    # Callbacks
    dp.add_handler(CallbackQueryHandler(handle_appeal))
    
    # Error handling
    dp.add_error_handler(lambda u, c: logger.error(u.error))
    
    updater.start_polling()
    logger.info("Bot started polling...")
    updater.idle()

if __name__ == '__main__':
    main()
    