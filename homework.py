import logging
import logging.handlers
import os
import time
from ast import arguments
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import UnexpectedStatusCode

load_dotenv()

logger = logging.getLogger(__name__)
format = (
    '%(asctime)s - %(levelname)s - %(name)s - '
    '%(funcName)s - %(lineno)s - %(message)s,'
),
logger.setLevel(logging.DEBUG)
STREAM_HANDLER = logging.StreamHandler()
STREAM_HANDLER.setFormatter(logging.Formatter(format))
STREAM_HANDLER.setLevel(logging.DEBUG)
ROTATING_HANDLER = logging.handlers.RotatingFileHandler(
    (__file__.rsplit('.', 1)[0] + '.log'), maxBytes=50000000, backupCount=5,)
ROTATING_HANDLER.setFormatter(logging.Formatter(format))
ROTATING_HANDLER.setLevel(logging.DEBUG)


logger.addHandler(ROTATING_HANDLER)
logger.addHandler(STREAM_HANDLER)
logger.debug('Логгер запущен')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

MESSAGE = 'Сообщение "{}" успешно отправлено.'


def send_message(bot, message):
    """Бот отправляет сообщение."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info(MESSAGE.format(message))


API_ERROR_DESCRIPTION = ('При выполнении запроса: {} с параметрами {},'
                         'произошла ошибка {}')
CONNECTION_ERROR = ('API ошибка запроса: {} закончился ошибкой {}')
UNEXPECTED_RESPONSE = ('Неожиданный ответ от сервера.'
                       'Сервер вернул ключ {}'
                       'Параметры запроса: {}'
                       'Содержание ответа:{}')


def get_api_answer(current_timestamp):
    """Функция делает запрос к API Яндекс практикума."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': current_timestamp}
        )
    except Exception as error:
        raise ConnectionError(CONNECTION_ERROR.format(response=response,
                                                      error=error))
    if response.status_code == HTTPStatus.OK:
        for key in response.json():
            if key != 'code' or 'error':
                return response.json()
            else:
                raise ValueError(UNEXPECTED_RESPONSE
                                 .format(key,
                                         response(arguments),
                                         response.json()))
    else:
        status_code = response.status_code
        raise UnexpectedStatusCode(API_ERROR_DESCRIPTION.
                                   format(response,
                                          response(arguments),
                                          status_code))


TYPE_NULL = 'В запросе нет такого ключа.'
TYPE_NOT_DICT = 'Ответ API не является словарем.'
TYPE_NOT_ISINSTANCE = 'Ответ API не является списком.'


def check_response(response):
    """Проверяем корректность ответа API."""
    if type(response) is not dict:
        raise TypeError(TYPE_NOT_DICT)
    try:
        homework = response['homeworks']
    except homework is None:
        raise KeyError(TYPE_NULL)
    if type(response['homeworks']) != list:
        raise TypeError(TYPE_NOT_ISINSTANCE)
    if not isinstance(homework, list):
        raise TypeError(TYPE_NOT_ISINSTANCE)

    # Без этой проверки не пропускают тесты
    return homework


UNEXPECTED_STATUS = 'Статус домашней работы {} отсутствует в ожидаемых.'
CHANGE_STATUS = 'Изменился статус проверки работы "{}". {}'


def parse_status(homework):
    """Возвращает статус домашнего задания."""
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_STATUSES[status]
    if status not in HOMEWORK_STATUSES:
        raise ValueError(UNEXPECTED_STATUS.format(status))
    return (CHANGE_STATUS.format(name, verdict))


TOKEN_ERROR = 'Отсутствует обязательная переменная окружения: {}'

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens():
    """Доступны переменные окружения."""
    for name in TOKENS:
        if globals()[name] is None:
            logger.critical(TOKEN_ERROR.format(name))
            return False
    return True


ENV_NONE = 'Отсутствие обязательных переменных окружения'
TOKEN_CHECK = 'Проверьте токены приложения'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(ENV_NONE)
        raise ValueError(TOKEN_CHECK)

    while True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            try:
                send_message(bot, message)
            except Exception as error:
                logger.exception(f'Не удалось отправить сообщение!'
                                 f'Произошла ошибка:{error}')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    main()
