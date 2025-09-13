from flask import Flask, render_template, request, redirect, url_for
from utils.file_ext import read_config, write_config
from modules import globals, client_manager, monitor

app = Flask(
    __name__,
    template_folder="src/html",
    static_folder="src"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config():
    cfg = read_config()
    return render_template("config.html", config=cfg)


@app.route("/save_config", methods=["POST"])
def save_config():
    data = request.form.items()
    write_config(data)
    return redirect(url_for("config"))


@app.route("/account")
async def account():
    await client_manager.load_sessions()

    monitor_accounts, clone_accounts = client_manager.get_session_info()

    return render_template("account.html",
                           monitor_accounts=monitor_accounts,
                           clone_accounts=clone_accounts)


@app.route("/login_all_session")
async def login_all_session():
    fut = client_manager.run_in_telethon_loop(client_manager.login_all_session())

    if fut.result():
        _, clone_accounts = client_manager.get_session_info()
        return {"clone": clone_accounts}, 200


@app.route("/logout_all_session")
async def logout_all_session():
    await client_manager.logout_all_session()
    _, clone_accounts = client_manager.get_session_info()

    return {"clone": clone_accounts}, 200


@app.route("/login_monitor_session")
async def login_monitor_session():
    fut = client_manager.run_in_telethon_loop(client_manager.login_monitor_session())

    if fut.result():
        monitor_accounts, _ = client_manager.get_session_info()

        return {"monitor": monitor_accounts}, 200


@app.route("/start")
async def start():
    fut = client_manager.run_in_telethon_loop(monitor.init_monitor())

    if fut.result():
        monitor_accounts, _ = client_manager.get_session_info()
        client_manager.run_in_telethon_loop(monitor.start())
        return {"monitor": monitor_accounts}, 200


@app.route("/cease")
async def cease():
    fut = client_manager.run_in_telethon_loop(monitor.cease())
    if fut.result():
        monitor_accounts, _ = client_manager.get_session_info()
        return {"monitor": monitor_accounts}, 200
