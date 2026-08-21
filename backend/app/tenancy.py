from contextvars import ContextVar

_business_id: ContextVar[int] = ContextVar("business_id", default=1)


def current_business_id() -> int:
    return _business_id.get()


def set_current_business_id(value: int):
    return _business_id.set(value)


def reset_current_business_id(token):
    _business_id.reset(token)
