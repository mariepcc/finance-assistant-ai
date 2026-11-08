class DomainError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    pass


class InvalidInputError(DomainError):
    pass


class ConsentRequiredError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class GoneError(DomainError):
    pass
