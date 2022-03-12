class UnexpectedStatusCode(Exception):
    """Сервер вернул статус-код который мы не ожидали."""

    def status_code_200(value):
        if value != 200:
            raise UnexpectedStatusCode(
                'Статус-код не соответствует значению 200')
