import secrets
import time


def new_id() -> str:
    return f"{int(time.time() * 1000)}-{secrets.token_hex(4)}"
