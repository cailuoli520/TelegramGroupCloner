import asyncio
from typing import Dict, Optional
from collections import defaultdict
from telethon import TelegramClient

clients_pool: Dict[TelegramClient, Optional[int]] = {}
client_locks: Dict[TelegramClient, asyncio.Lock] = {}
sender_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
monitor_client = TelegramClient
message_id_mapping: Dict[int, int] = {}
sessions_pool = {}
telethon_loop = asyncio.new_event_loop()
config_path = 'setting/config.ini'
