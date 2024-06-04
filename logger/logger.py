import logging


# formatter_line = '%(asctime)s %(name)s %(levelname)s: %(filename)s:%(lineno)d %(message)s'
formatter_line = '%(asctime)s %(name)s %(lineno)d, %(levelname)s:  %(message)s'


def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(formatter_line, datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
