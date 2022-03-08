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
    level=logging.INFO,
    filename='bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
# Устанавливаем уровень, с которого логи будут сохраняться в файл
logger.setLevel(logging.INFO)
# Указываем обработчик логов
handler = RotatingFileHandler('bot.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)

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
    logging.info('Сообщение успешно отправлено.')


def get_api_answer(current_timestamp):
    """Функция делает запрос к API Яндекс практикума."""
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            status_code = response.status_code
            logger.error(f'Ошибка {status_code}')
            raise ConnectionError(f'Ошибка {status_code}')
    except ValueError:
        logger.error('Ошибка при формировании json (response)')
        raise ValueError('Ошибка при формировании json(response)')
    except Exception as error:
        logger.error(f'API ошибка запроса: {error}')
        raise Exception(f'API ошибка запроса: {error}')


def check_response(response):
    """Проверяем корректность ответа API"""
    if type(response) != dict:
        raise TypeError('Ответ API имеет неверный тип данных.')
    elif type(response['homeworks']) != list:
        raise TypeError('Домашние задания приходят не в виде списка.')
    elif len(response['homeworks']) == 0:
        raise Empty('В ответе от API нет новых домашних заданий.')
    homework = response.get('homeworks')
    return homework


def parse_status(homework):
    """Возвращает статус домашнего задания"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Доступны переменные окружения."""
    token_list = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    if not all(token_list):
        message = 'Отсутствует или не задана переменная окружения.'
        logging.critical(message)
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""

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
                logging.info('Удачная отправка сообщения в Telegram.')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            logging.error('Другие сбои при запросе к эндпоинту.')
        logger.info('Бот начал работу.')


if __name__ == '__main__':
    main()
