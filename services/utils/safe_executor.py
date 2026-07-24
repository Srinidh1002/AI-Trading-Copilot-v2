"""
Safe Execution Helper
"""
from services.utils.logger import logger

def safe_execute(func, default=None, *args, **kwargs):

    try:

        return func(*args, **kwargs)

    except Exception as e:

        logger.exception(
            f"{func.__name__} failed: {e}"
        )

        return default