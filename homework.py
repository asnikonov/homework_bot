import logging
import logging.handlers
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException

from exceptions import UnexpectedStatusCode

load_dotenv()

logger = logging.getLogger(__name__)
format = (
    '%(asctime)s - %(levelname)s - %(name)s - '
    '%(funcName)s - %(lineno)s - %(message)s,'
),
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter(format))
stream_handler.setLevel(logging.DEBUG)
rotating_handler = logging.handlers.RotatingFileHandler(
    (__file__.rsplit('.', 1)[0] + '.log'), maxBytes=50000000, backupCount=5,)
rotating_handler.setFormatter(logging.Formatter(format))
rotating_handler.setLevel(logging.DEBUG)


logger.addHandler(rotating_handler)
logger.addHandler(stream_handler)
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


API_ERROR_DESCRIPTION = ('При выполнении запроса с параметрами {}, {}, {},'
                         'произошла ошибка. Код ошибки: {}')
CONNECTION_ERROR = (
    'API запрос с параметрами: {}, {}, {}, закончился ошибкой {}')
UNEXPECTED_RESPONSE = ('Неожиданный ответ от сервера.'
                       'Параметры запроса: {}, {}, {}'
                       'Получен ключ: {}, со значением: {}')


def get_api_answer(current_timestamp):
    """Функция делает запрос к API Яндекс практикума."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except RequestException as error:
        raise ConnectionError(
            CONNECTION_ERROR.format(ENDPOINT, params, HEADERS, error))
    saved_json = response.json()
    error_keys = ('code', 'error')
    status_code = response.status_code
    if response.status_code != HTTPStatus.OK:
        raise UnexpectedStatusCode(API_ERROR_DESCRIPTION.
                                   format(ENDPOINT,
                                          HEADERS,
                                          params,
                                          status_code))
    for key in error_keys:
        if key in saved_json:
            raise ValueError(UNEXPECTED_RESPONSE
                             .format(ENDPOINT,
                                     HEADERS,
                                     params,
                                     key,
                                     saved_json[key]))
    return saved_json


KEY_MISSING = 'В запросе нет ключа {}.'
TYPE_NOT_DICT = 'Ответ API не является словарем.'
RESPONSE_NOT_LIST = 'Ответ API не содержит список.'


def check_response(response):
    """Проверяем корректность ответа API."""
    if type(response) is not dict:
        raise TypeError(TYPE_NOT_DICT)
    homework = response['homeworks']
    if 'homeworks' not in response:
        raise KeyError(KEY_MISSING.format(homework))
    if not isinstance(homework, list):
        raise TypeError(RESPONSE_NOT_LIST)

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
    return CHANGE_STATUS.format(name, verdict)


TOKEN_ERROR = 'Отсутствует обязательная переменная окружения: {}'

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens():
    """Доступны переменные окружения."""
    name_in_globals = True
    for name in TOKENS:
        if globals()[name] is None:
            name_in_globals = False
            logger.critical(TOKEN_ERROR.format(name))
    return name_in_globals


ENV_NONE = 'Отсутствие обязательных переменных окружения'
TOKEN_CHECK = 'Проверьте токены приложения'
PROGRAMM_ERROR = 'Сбой в работе программы: {}'
MESSAGE_ERROR = ('Не удалось отправить сообщение "{}".'
                 'Произошла ошибка: {}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(ENV_NONE)
        raise ValueError(TOKEN_CHECK)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = PROGRAMM_ERROR.format(error)
            logger.exception(message)
            try:
                send_message(bot, message)
            except Exception as error:
                logger.exception(MESSAGE_ERROR.format(message, error))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':

    main()
