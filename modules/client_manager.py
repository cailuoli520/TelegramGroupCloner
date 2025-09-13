import asyncio
import os

from typing import Union, Tuple, List, Dict, Any, Optional
from telethon import TelegramClient
from telethon.tl.functions.photos import DeletePhotosRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputPhoto
from telethon.tl.functions.account import UpdateProfileRequest, UpdateEmojiStatusRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.types import User
from utils.file_ext import Config
from utils.log import logger

from modules.globals import sessions_pool, clients_pool, client_locks, telethon_loop
from modules import globals


async def login_client(file_path: str) -> Union[TelegramClient, bool]:
    logger.info(f"正在加载: {file_path}")

    client = TelegramClient(f"{file_path}", Config.API_ID, Config.API_HASH, proxy=Config.PROXY, loop=telethon_loop)
    await client.connect()

    if await client.is_user_authorized():
        logger.info(f"加载成功: {file_path}")
        return client
    else:
        await client.disconnect()
        await cleanup_not_authorized_client(file_path)
        return False


async def update_profile(client: TelegramClient, monitor_client: TelegramClient, sender: User, phone: str) -> None:
    sender_id = sender.id
    try:
        await client(UpdateProfileRequest(
            first_name=sender.first_name or " ",
            last_name=sender.last_name or "",
        ))
        logger.info(f"[{phone}] 设置昵称成功: {sender_id}")

        photos = await monitor_client.get_profile_photos(sender, limit=1)
        if photos:
            profile_path = await monitor_client.download_media(photos[0])
            if profile_path and os.path.exists(profile_path):
                uploaded = await client.upload_file(file=profile_path)

                if photos[0].video_sizes:
                    await client(UploadProfilePhotoRequest(video=uploaded))
                else:
                    await client(UploadProfilePhotoRequest(file=uploaded))

                os.remove(profile_path)

                logger.info(f"[{phone}] 设置头像成功: {sender_id}")
            else:
                logger.warning(f"[{phone}] 头像无法下载: {sender_id}")
        else:
            logger.info(f"[{phone}] 用户未设置头像: {sender_id}")
        if sender.emoji_status:
            me = await client.get_me()
            if me.premium:
                await client(UpdateEmojiStatusRequest(sender.emoji_status))
                logger.info(f"[{phone}] 设置Emoji状态成功: {sender_id}，如果是礼物状态则无法设置")
        else:
            logger.info(f"[{phone}] 用户未设置状态: {sender_id}")

    except Exception as e:
        logger.error(f"设置资料出现错误: {e}")


async def cleanup_not_authorized_client(session_name):
    try:
        os.remove(f"{session_name}")
        logger.info(f"清理未授权session成功 {session_name}")
    except PermissionError:
        logger.warning(f"清理未授权session失败 {session_name}，文件正在使用中")


async def cleanup_frozen_client(client: TelegramClient) -> None:
    try:
        phone = (await client.get_me()).phone
        logger.info(f"[{phone}] 被冻结")

        await client.disconnect()

        clients_pool.pop(client, None)
        await client_locks.pop(client, None)

    except Exception as e:
        logger.error(f"清理被冻结账号失败: {e}")


async def load_sessions() -> None:
    if sessions_pool:
        return

    for file_name in os.listdir("sessions"):
        if not file_name.endswith(".session"):
            continue

        session_name = file_name.replace(".session", "")

        if session_name in sessions_pool:
            continue

        sessions_pool[session_name] = {
            "type": "clone"
        }

    if os.path.exists("monitor.session") and "monitor" not in sessions_pool:
        sessions_pool["monitor"] = {
            "type": "monitor"
        }


async def login_all_session() -> bool:
    for filename in os.listdir("sessions"):
        if filename.endswith(".session"):
            session_name = filename.replace(".session", "")

            client = await login_client(f"sessions/{filename}")

            if client:
                clients_pool[client] = None
                client_locks[client] = asyncio.Lock()

                me = await client.get_me()

                sessions_pool[session_name].update({
                    "phone": me.phone,
                    "username": me.username or "",
                    "nickname": me.first_name or "" + me.last_name or "",
                    "status": "在线",
                })
    return True


async def login_monitor_session() -> bool:
    file_path = "monitor.session"

    client = await login_client(file_path)

    if client:
        globals.monitor_client = client
        me = await client.get_me()
        sessions_pool["monitor"].update({
            "phone": me.phone,
            "username": me.username or "",
            "nickname": me.first_name or "" + me.last_name or "",
            "status": "在线",
        })

    return True


async def logout_all_session() -> None:
    for session_name, info in sessions_pool.items():
        try:
            if info.get("type") == "monitor":
                continue

            client = None
            for c in clients_pool.keys():
                if c.session.filename.endswith(f"{session_name}.session"):
                    client = c
                    break

            if client:
                await client.disconnect()
                clients_pool.pop(client, None)
                client_locks.pop(client, None)

                info["status"] = "离线"
                logger.info(f"{session_name} 离线成功")

        except Exception as e:
            logger.warning(f"{session_name} 离线失败: {e}")


def get_session_info() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    monitor_accounts = []
    clone_accounts = []
    idx1, idx2 = 1, 1

    for session_name, info in sessions_pool.items():
        if session_name == "monitor":
            monitor_accounts.append({
                "id": idx1,
                "session": session_name,
                "phone": info.get("phone", ""),
                "username": info.get("username", ""),
                "nickname": info.get("nickname", ""),
                "status": info.get("status", "")
            })
            idx1 += 1
        else:
            clone_accounts.append({
                "id": idx2,
                "session": session_name,
                "phone": info.get("phone", ""),
                "username": info.get("username", ""),
                "nickname": info.get("nickname", ""),
                "status": info.get("status", "")
            })
            idx2 += 1

    return monitor_accounts, clone_accounts


async def delete_profile_photos(client: TelegramClient) -> None:
    try:
        me = await client.get_me()
        photos = await client.get_profile_photos(me.id)
        for photo in photos:
            await client(DeletePhotosRequest([
                InputPhoto(
                    id=photo.id,
                    access_hash=photo.access_hash,
                    file_reference=photo.file_reference
                )]))
        logger.info(f"[{me.phone}] 清空历史头像成功")
    except Exception as e:
        if "FROZEN_METHOD_INVALID" in str(e):
            await cleanup_frozen_client(client)
            logger.error(f"清空历史头像失败，账号被冻结")
        else:
            logger.info(e)


async def check_and_join_target(client: TelegramClient) -> None:
    try:
        await client(JoinChannelRequest(Config.TARGET_GROUP))
        me = await client.get_me()
        logger.info(f"[{me.phone}] 加入目标群组成功")
    except Exception as e:
        if "FROZEN_METHOD_INVALID" in str(e):
            await cleanup_frozen_client(client)
            logger.error(f"克隆账号加入目标群组失败，账号被冻结")
        else:
            logger.info(e)


async def check_and_join_source(client: TelegramClient) -> None:
    try:
        for group in Config.SOURCE_GROUPS:
            await client(JoinChannelRequest(group))
        logger.info("监听账号加入源群组成功")
    except Exception as e:
        if "FROZEN_METHOD_INVALID" in str(e):
            await cleanup_frozen_client(client)
            logger.error(f"监听账号加入源群组失败，账号被冻结")


def run_telethon_loop():
    asyncio.set_event_loop(telethon_loop)
    telethon_loop.run_forever()


def run_in_telethon_loop(coro):
    return asyncio.run_coroutine_threadsafe(coro, telethon_loop)
