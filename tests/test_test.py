import logging.config
import pytest

@pytest.fixture(scope='session', autouse=True)
def configure_logging():
    # Load the test-specific logging configuration
    logging.config.fileConfig('./logging_test.ini')


# @pytest.fixture(scope='session', autouse=True)
# def configure_logging():
#     logging.basicConfig(level=logging.DEBUG)


def test_logging():
    logging.debug("This is a debug message")
    logging.info("This is an info message")
    logging.warning("This is a warning message")
    logging.error("This is an error message")
    logging.critical("This is a critical message")
