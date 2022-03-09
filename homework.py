import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from queue import Empty

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot.log',
    format=(
        '%(asctime)s - %(levelname)s - %(name)s - '
        '%(funcName)s - %(lineno)s - %(message)s,'
    ),
    filemode='w'
)

logger = logging.getLogger(__name__)
# Устанавливаем уровень, с которого логи будут сохраняться в файл
# Указываем обработчик логов
handler = RotatingFileHandler(
    __file__ + '.log', maxBytes=50000000, backupCount=5,)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - '
    '%(funcName)s - %(lineno)s - %(message)s,'
),
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

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


def send_message(bot, message):
    """Бот отправляет сообщение."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.info('Сообщение о статусе работы успешно отправлено.')


def get_api_answer(current_timestamp):
    """Функция делает запрос к API Яндекс практикума."""
    try:
        params = {'from_date': current_timestamp}
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if response.status_code == HTTPStatus.OK:
            try:
                return response.json()
            except Exception:
                raise('Повторите попытку позже')
        status_code = response.status_code
        logging.error(f'Ошибка {status_code}')
        raise ConnectionError(f'Ошибка {status_code}')
    except Exception as error:
        logging.error(f'API ошибка запроса: {error}')
        raise Exception(f'API ошибка запроса: {error}')


def check_response(response):
    """Проверяем корректность ответа API."""
    homeworks = response['homeworks']
    if homeworks is None or not isinstance(homeworks, list):
        raise TypeError('Ответ API имеет неверный тип данных.')
    elif type(response['homeworks']) != list:
        raise TypeError('Домашние задания приходят не в виде списка.')
    elif len(response['homeworks']) == 0:
        raise Empty('В ответе от API нет новых домашних заданий.')
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Возвращает статус домашнего задания."""
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_STATUSES[status]
    if status not in HOMEWORK_STATUSES.keys():
        raise ValueError(f'Статус домашней работы {status} некорректен.')
    return f'Изменился статус проверки работы "{name}". {verdict}'


def check_tokens():
    """Доступны переменные окружения."""
    token_list = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    for token in token_list:
        if token is None:
            logging.critical(f'Токен{token} не задан!.')
            return False
    logging.info('Проверка токенов: ОК')
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())

    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных окружения')
        raise ('Проверьте токены приложения')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            try:
                send_message(bot, message)
            except Exception:
                logging.exception('Не удалось отправить сообщение!'
                                  'Повторите попытку позже')
            time.sleep(RETRY_TIME)
            logging.error(f'{message}')
        logging.info('Бот начал работу.')


if __name__ == '__main__':
    main()
