import logging
import logging.handlers
import os
import time
from http import HTTPStatus
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
format = (
    '%(asctime)s - %(levelname)s - %(name)s - '
    '%(funcName)s - %(lineno)s - %(message)s,'
),
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(format))
sh.setLevel(logging.DEBUG)
rh = logging.handlers.RotatingFileHandler(
    (__file__.rsplit('.', 1)[0] + '.log'), maxBytes=50000000, backupCount=5,)
rh.setFormatter(logging.Formatter(format))
rh.setLevel(logging.DEBUG)


logger.addHandler(rh)
logger.addHandler(sh)
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


API_ERROR_DESC = 'При выполнении запроса: {response}, произошла ошибка {code}'
CONNECTION_ERROR = 'API ошибка запроса: {response} закончился ошибкой {error}'


def get_api_answer(current_timestamp):
    """Функция делает запрос к API Яндекс практикума."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': current_timestamp}
        )
        if response.status_code == HTTPStatus.OK:
            if 'code' in response.json():
                raise ValueError(f'Неожиданный ответ от сервера.'
                                 f'Содержание ответа:{response.json()}')
            elif 'error' in response.json():
                raise ValueError(f'Неожиданный ответ от сервера.'
                                 f'Содержание ответа:{response.json()}')
            else:
                return response.json()
        else:
            status_code = response.status_code
            raise HTTPError(API_ERROR_DESC.format(response=response,
                                                  code=status_code))
    except ConnectionError as error:
        raise ConnectionError(CONNECTION_ERROR.format(response=response,
                                                      error=error))


TYPE_NULL = 'Ответ API вернул пустой список.'
TYPE_NOT_DICT = 'Ответ API не является словарем.'
TYPE_NOT_ISINSTANCE = 'Ответ API не является списком.'


def check_response(response):
    """Проверяем корректность ответа API."""
    if type(response) is not dict:
        raise TypeError(TYPE_NOT_DICT)
    try:
        homework = response['homeworks']
    except homework is None:
        raise TypeError(TYPE_NULL)
    except homework is not isinstance(homework, list):
        raise TypeError(TYPE_NOT_ISINSTANCE)
    if type(response['homeworks']) != list:
        raise TypeError(TYPE_NOT_ISINSTANCE)
    # Без этой проверки не пропускают тесты
    return homework


UNEXPECTED_HW = 'Ответ API вернул неизвестную домашнюю работу.'
UNEXPECTED_STATUS = 'Ответ API вернул неизвестный статус домашней работы.'


PHRASE = 'Статус домашней работы {status} отсутствует в ожидаемых.'


def parse_status(homework):
    """Возвращает статус домашнего задания."""
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_STATUSES[status]
    if status not in HOMEWORK_STATUSES.keys():
        raise ValueError(PHRASE.format(status=status))
    return (f'Изменился статус проверки работы "{name}". {verdict}')


TOKEN_ERROR = 'Отсутствует обязательная переменная окружения: {key}'


def check_tokens():
    """Доступны переменные окружения."""
    TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    # При выносе этого блока на уровень модуля, падают тесты
    for key, value in TOKENS.items():
        if value is None:
            logger.critical(TOKEN_ERROR.format(key=key))
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствие обязательных переменных окружения')
        raise ValueError('Проверьте токены приложения')

    while True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
                time.sleep(RETRY_TIME)
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

    logging.basicConfig(
        level=logging.DEBUG,
        filename=(__file__.rsplit('.', 1)[0] + '.log'),
        format=(
            '%(asctime)s - %(levelname)s - %(name)s - '
            '%(funcName)s - %(lineno)s - %(message)s,'
        ),
        filemode='w'
    )
    main()
