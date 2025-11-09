import logging
import os
from random import choice
from enum import Enum, auto

import redis
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
    ConversationHandler,
)

from quiz_utils import Button, DATA_DIR, load_all, normalize_text, strip_explanation


class QuizState(Enum):
    CHOOSING = auto()
    ANSWERING = auto()


def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [KeyboardButton(Button.NEW_QUESTION.value), KeyboardButton(Button.GIVE_UP.value)],
        [KeyboardButton(Button.MY_SCORE.value)],
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('Привет, я бот для викторин!', reply_markup=markup)
    return QuizState.CHOOSING


def handle_new_question_request(update: Update, context: CallbackContext) -> None:
    redis_client = context.bot_data['redis']
    question = choice(load_all(DATA_DIR))
    user_id = update.effective_user.id
    redis_client.hset(f'user:{user_id}', mapping={
        'question': question['question'],
        'answer': question['answer'],
        })
    update.message.reply_text(question['question'])
    return QuizState.ANSWERING


def handle_solution_attempt(update: Update, context: CallbackContext) -> None:
    redis_client = context.bot_data['redis']
    user_id = update.effective_user.id
    storage_key = f'user:{user_id}'
    db = redis_client.hgetall(storage_key)

    normalize_correct = normalize_text(strip_explanation(db.get('answer')))
    normalize_user = normalize_text(strip_explanation(update.message.text))

    if normalize_user == normalize_correct:
        redis_client.hdel(storage_key, 'question', 'answer')
        update.message.reply_text(
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»'
            )
        return QuizState.CHOOSING
    else:
        update.message.reply_text('Неправильно… Попробуешь ещё раз?')
        return QuizState.ANSWERING


def handle_give_up(update: Update, context: CallbackContext) -> None:
    redis_client = context.bot_data['redis']
    user_id = update.effective_user.id
    storage_key = f'user:{user_id}'
    db = redis_client.hgetall(storage_key)
    answer = db.get('answer')

    if not answer:
        update.message.reply_text('Сначала запроси новый вопрос, нажав «Новый вопрос»')
        return QuizState.CHOOSING

    update.message.reply_text(f'Правильный ответ: {answer}')
    redis_client.hdel(storage_key, 'question', 'answer')
    return handle_new_question_request(update, context)


def run_tg_bot(redis_url, token):
    redis_client = redis.from_url(redis_url, decode_responses=True)
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.bot_data['redis'] = redis_client

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            QuizState.CHOOSING: [
                MessageHandler(Filters.regex(f'^{Button.NEW_QUESTION.value}$'),
                               handle_new_question_request),
                MessageHandler(Filters.regex(f'^{Button.GIVE_UP.value}$'), handle_give_up),
            ],
            QuizState.ANSWERING: [
                MessageHandler(Filters.regex(f'^{Button.GIVE_UP.value}$'), handle_give_up),
                MessageHandler(Filters.text & ~Filters.command, handle_solution_attempt),
            ],
        },
        fallbacks=[],
        name='quiz',
        persistent=False
    )

    dispatcher.add_handler(conv_handler)

    logging.info('TG Bot is starting...')
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    load_dotenv()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
    token = os.getenv('TG_BOT_TOKEN')
    if not token:
        logging.error('TG_BOT_TOKEN не найден в переменных окружения.')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    run_tg_bot(redis_url, token)
