from logging import handlers


def test_timed_rotating_file_handler_available():
    assert hasattr(handlers, 'TimedRotatingFileHandler'), "TimedRotatingFileHandler class not found in logging.handlers"
