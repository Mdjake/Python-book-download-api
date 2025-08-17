import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import urllib.parse

# Function to fetch first book link after Telegram link
def fetch_book_link(book_name):
    formatted_name = urllib.parse.quote_plus(book_name)
    search_url = f"https://pdfdrive.com.co/search/{formatted_name}/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract all links
    all_links = [a.get("href") for a in soup.find_all("a", href=True)]

    # Find Telegram link index
    telegram_index = None
    for i, link in enumerate(all_links):
        if "t.me/" in link:
            telegram_index = i
            break

    # First book link after Telegram link
    if telegram_index is not None and telegram_index + 1 < len(all_links):
        return all_links[telegram_index + 1]
    return None

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me the name of the book and I will try to get the PDF download link for you."
    )

# Handle messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    book_name = update.message.text
    await update.message.reply_text(f"Searching for '{book_name}'...")
    link = fetch_book_link(book_name)
    if link:
        await update.message.reply_text(f"First book link found: {link}")
    else:
        await update.message.reply_text("Could not find book link after Telegram link.")

if __name__ == "__main__":
    TOKEN = "7316069369:AAEDqbdFir0pfP2lwOjLtlhT40IH7LwRebw"  # Replace with your bot token
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()
