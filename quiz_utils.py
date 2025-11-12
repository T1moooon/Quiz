import re
from enum import Enum
from pathlib import Path

FOLDER_PATH = Path("quiz-questions")
PATTERN = re.compile(
    r"Вопрос \d+:\s*(.*?)\nОтвет:\s*(.*?)(?=\n(?:[А-ЯЁ][^:\n]+:|Вопрос \d+:)|\Z)",
    re.S
    )
ANSWER_RE = re.compile(r'^[^.(]+')


class Button(Enum):
    NEW_QUESTION = 'Новый вопрос'
    GIVE_UP = 'Сдаться'
    MY_SCORE = 'Мой счёт'


def strip_explanation(text):
    if not text:
        return ''
    match = ANSWER_RE.match(text)
    return match.group(0).strip() if match else text.strip()


def normalize_text(text):
    if not text:
        return ''
    return ' '.join(text.lower().strip().split())


def load_file(path: Path):
    text = path.read_text(encoding="koi8-r")
    pairs = []
    for question, answer in PATTERN.findall(text):
        pairs.append(
            {
                "question": " ".join(question.split()),
                "answer": " ".join(answer.split()),
            }
        )
    return pairs


def load_all_questions(data_dir: Path):
    result = []
    for path in sorted(data_dir.glob("*.txt")):
        try:
            result.extend(load_file(path))
        except UnicodeDecodeError:
            pass
    return result
