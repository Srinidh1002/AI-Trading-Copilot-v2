from config import DEBUG_MODE


def debug_print(*args, **kwargs):
    if DEBUG_MODE:
        print(*args, **kwargs)