class UnexpectedStatusCode(Exception):
    """Сервер вернул статус-код который мы не ожидали."""

    pass


class EmptyList(Exception):
    """Сервер вернул пустой список."""

    pass
