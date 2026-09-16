from typing import Any

from fastapi import Request


def get_runtime(request: Request) -> Any:
    return request.app.state.runtime
