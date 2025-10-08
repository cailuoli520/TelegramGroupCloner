import asyncio
from asyncio import Queue, AbstractEventLoop
from typing import Dict, Optional
from collections import defaultdict
from telethon import TelegramClient
from telethon.tl.custom.message import Message

clients_pool: Dict[TelegramClient, Optional[int]] = {}
client_locks: Dict[TelegramClient, asyncio.Lock] = {}
sender_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
monitor_client: Optional[TelegramClient] = None
message_id_mapping: Dict[int, int] = {}
sessions_pool: Dict = {}
telethon_loop: AbstractEventLoop = asyncio.new_event_loop()
message_queue: Queue[Message] = Queue()
phone_data: Dict[str, str] = {}
config_path: str = "setting/config.ini"
log_path: str = "logs/app.log"
profile_photos_path: str = "profile_photos"
media_path: str = "downloads"
