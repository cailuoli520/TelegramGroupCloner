import os
import threading

from utils.file_ext import load_config, init_files
from modules.client_manager import run_telethon_loop
from web.app import app


def main():
    # os.system(f"start http://127.0.0.1:5000")
    threading.Thread(target=run_telethon_loop, daemon=True).start()
    init_files()
    load_config()


if __name__ == "__main__":
    main()
    app.run(debug=True)
