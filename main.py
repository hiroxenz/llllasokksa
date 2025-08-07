import telebot
import os

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Halo! Bot aktif di Railway.")

@bot.message_handler(func=lambda m: True)
def echo(message):
    bot.reply_to(message, message.text)

if __name__ == "__main__":
    bot.infinity_polling()
