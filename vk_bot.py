import logging
import os
import random
from random import choice

import redis
import vk_api as vk
from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType, VkLongPoll

from quiz_utils import (
    FOLDER_PATH,
    Button,
    load_all_questions,
    normalize_text,
    strip_explanation,
)


def build_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button(Button.NEW_QUESTION.value, color=VkKeyboardColor.PRIMARY)
    keyboard.add_button(Button.GIVE_UP.value, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(Button.MY_SCORE.value, color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def send_message(vk_api, user_id, message) -> None:
    vk_api.messages.send(
        user_id=user_id,
        message=message,
        random_id=random.randint(1, 1_000_000_000),
        keyboard=build_keyboard(),
    )


def _storage_key(user_id):
    return f'user:{user_id}'


def handle_new_question_request(vk_api, redis_client, user_id) -> None:
    question = choice(load_all_questions(FOLDER_PATH))
    redis_client.hset(
        _storage_key(user_id),
        mapping={'question': question['question'], 'answer': question['answer']},
    )
    send_message(vk_api, user_id, question['question'])


def handle_solution_attempt(vk_api, redis_client, user_id, text) -> None:
    db = redis_client.hgetall(_storage_key(user_id))
    correct_answer = db.get('answer')
    if not correct_answer:
        send_message(vk_api, user_id, 'Сначала запроси вопрос кнопкой «Новый вопрос».')
        return

    normalized_correct = normalize_text(strip_explanation(correct_answer))
    normalized_user = normalize_text(strip_explanation(text))

    if normalized_user == normalized_correct:
        redis_client.hdel(_storage_key(user_id), 'question', 'answer')
        send_message(
            vk_api,
            user_id,
            'Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос».',
        )
    else:
        send_message(vk_api, user_id, 'Неправильно… Попробуешь ещё раз?')


def handle_give_up(vk_api, redis_client, user_id) -> None:
    db = redis_client.hgetall(_storage_key(user_id))
    answer = db.get('answer')
    if not answer:
        send_message(vk_api, user_id, 'Нет активного вопроса. Нажми «Новый вопрос».')
        return

    send_message(vk_api, user_id, f'Правильный ответ: {answer}')
    redis_client.hdel(_storage_key(user_id), 'question', 'answer')
    handle_new_question_request(vk_api, redis_client, user_id)


def vk_run_bot(redis_url, token):
    redis_client = redis.from_url(redis_url, decode_responses=True)

    vk_session = vk.VkApi(token=token)
    vk_api = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    logging.info('VK Bot is starting...')
    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        text = event.text.strip()
        if not text:
            continue

        if text == Button.NEW_QUESTION.value:
            handle_new_question_request(vk_api, redis_client, event.user_id)
        elif text == Button.GIVE_UP.value:
            handle_give_up(vk_api, redis_client, event.user_id)
        else:
            handle_solution_attempt(vk_api, redis_client, event.user_id, text)


if __name__ == '__main__':
    load_dotenv()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
    token = os.getenv('VK_BOT_TOKEN')
    if not token:
        logging.error('VK_BOT_TOKEN не найден в переменных окружения.')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    vk_run_bot(redis_url, token)
