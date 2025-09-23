import asyncio
import os
import threading

from utils.file_ext import load_config, init_files
from modules.client_manager import run_telethon_loop
from web.app import app


async def main():
    threading.Thread(target=run_telethon_loop, daemon=True).start()
    await init_files()
    await load_config()


if __name__ == "__main__":
    asyncio.run(main())
    os.system(f"start http://127.0.0.1:5000")
    app.run()
