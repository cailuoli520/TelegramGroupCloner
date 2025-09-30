import logging
import os

os.makedirs("logs", exist_ok=True)
logging.getLogger('telethon').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('Flask').setLevel(logging.ERROR)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("logs/app.log", encoding="gbk"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
