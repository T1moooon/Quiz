import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Здравствуйте')


def echo(update: Update, context: CallbackContext) -> None:
    if update.message and update.message.text is not None:
        update.message.reply_text(update.message.text)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )

    token = os.getenv('TG_BOT_TOKEN')
    if not token:
        logging.error(
            'TG_BOT_TOKEN не найден в переменных окружения.'
        )

    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    logging.info('Echo bot is starting...')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
