import multiprocessing
import logging
import os
import sys
import controller

file_handler = logging.FileHandler(filename='tmp.log')
stdout_handler = logging.StreamHandler(stream=sys.stdout)
handlers = [file_handler, stdout_handler]

logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)
app = controller.app # Flask run initializes server.

if __name__ ==  '__main__':
    logger.info("starting")

    app.run(port=5051, debug=False, host='0.0.0.0')