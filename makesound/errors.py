class MakeSoundError(Exception):
    """Only static, safe messages may cross the CLI boundary."""

    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def require(condition, code="invalid_data", message="Data validation failed."):
    if not condition:
        raise MakeSoundError(code, message)
