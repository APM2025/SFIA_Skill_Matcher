from app.services.framework_parser import get_framework_parser
import logging

logging.basicConfig(level=logging.DEBUG)
parser = get_framework_parser()
if parser:
    print(parser.loaded_frameworks)
else:
    print("Parser is None")
