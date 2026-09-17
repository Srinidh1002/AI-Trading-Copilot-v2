import sys, logging
sys.path.append('src')
from src.sensitive_filter import SensitiveFilter

# Simulate a leak scenario
logger = logging.getLogger("leaktest")
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler(sys.stdout)
h.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(h)
logger.addFilter(SensitiveFilter(["SECRET_KEY_XYZ123", "my-password"]))

# These should print with the secrets redacted
logger.info("Connecting with api_key=SECRET_KEY_XYZ123")
logger.info("Auth attempt for user with password=my-password")
logger.info("Normal message with no secrets")
