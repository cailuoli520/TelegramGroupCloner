import asyncio
import os

from modules.error_handing import error_handle
from modules.globals import sender_locks, clients_pool, message_id_mapping, sessions_pool, message_queue, \
    media_path
from modules import globals
from modules.client_manager import cleanup_frozen_client, update_profile, check_and_join_source, load_session
from telethon import TelegramClient, events
from telethon.tl.custom.message import Message
from telethon.tl.types import MessageMediaPhoto
from utils.log import logger
from utils.file_ext import Config


async def clone_and_forward_message(event: Message) -> None:
    sender = await event.get_sender()
    if not sender or sender.bot:
        return

    sender_id = sender.id
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()

    if sender_id in Config.USER_IDS:
        logger.info(f"ID在黑名单中: {sender_id}")
        return

    if any(keyword in event.message.text for keyword in Config.KEYWORDS):
        logger.info(f"消息包含黑名单关键词: {sender_id}")
        return

    if any(name in full_name for name in Config.NAMES):
        logger.info(f"昵称包含黑名单名称: {sender_id}")
        return

    for client, cloned_user in clients_pool.items():
        if cloned_user == sender_id:
            # 已分配过的 client
            try:
                me = await client.get_me()
                await forward_message_as(
                    client, event)
                logger.info(f"[{me.phone}] 转发新消息: {sender_id}")
            except Exception as e:
                if "FROZEN_METHOD_INVALID" in str(e):
                    await cleanup_frozen_client(client, sender_id)
                logger.error(f"转发失败（已克隆用户）: {e}")
            return
        elif cloned_user is None:
            # 未分配过的 client
            try:
                await globals.monitor_client.get_input_entity(sender_id)
                me = await client.get_me()
                phone = me.phone

                logger.info(f"[{phone}] 正在克隆新用户: {sender_id}")

                clients_pool[client] = sender_id

                await forward_message_as(client, event)

                await update_profile(client, globals.monitor_client, sender, phone)

                logger.info(f"[{phone}] 完成新用户克隆: {sender_id}")
            except ValueError:
                logger.error(f"用户无法解析: {sender_id}")
            except Exception as e:
                if "FROZEN_METHOD_INVALID" in str(e):
                    await cleanup_frozen_client(client, sender_id)
                logger.error(f"克隆失败: {e}")
            return

    logger.warning("无可用账号进行克隆")


async def forward_message_as(client: TelegramClient, event) -> None:
    message = event.message
    text = apply_replacements(message.text or "")
    target_group = Config.TARGET_GROUP
    try:
        if message.is_reply:
            await send_reply_message(client, event, target_group, message, text)
        else:
            await send_regular_message(client, target_group, message, text)
    except Exception as e:
        logger.error(f"获取当前用户信息失败: {e}")


async def send_regular_message(client: TelegramClient, target_group, message: Message, text: str):
    try:
        media = message.media
        if media:
            file_path = await globals.monitor_client.download_media(message, f"{media_path}/{message.id}")
            if isinstance(media, MessageMediaPhoto):
                sent = await client.send_file(
                    target_group,
                    file_path,
                    caption=text
                )
            else:
                sent = await client.send_file(
                    target_group,
                    file_path,
                    attributes=message.media.document.attributes,
                    caption=text
                )
            os.remove(file_path)
        else:
            sent = await client.send_message(
                target_group,
                text
            )

        message_id_mapping[message.id] = sent.id
    except Exception as e:
        msg = await error_handle(e)
        logger.error(f"发送当前消息失败: {msg}")


async def send_reply_message(client: TelegramClient, event, target_group, message: Message, text: str):
    try:
        reply = await event.get_reply_message()
        if not reply:
            logger.warning("无法获取被回复消息")
            return

        logger.info(f"找到被回复消息: {reply.id}, 来自: {reply.sender_id}")

        if reply.id in message_id_mapping:
            reply_to_msg_id = message_id_mapping[reply.id]
        else:
            logger.info("没有找到对应的克隆账号消息，跳过回复")
            return
        media = message.media
        if media:
            file_path = await globals.monitor_client.download_media(message, f"{media_path}/{message.id}")
            if isinstance(media, MessageMediaPhoto):
                sent_reply = await client.send_file(
                    target_group,
                    file_path,
                    caption=text
                )
            else:
                sent_reply = await client.send_file(
                    target_group,
                    file_path,
                    attributes=message.media.document.attributes,
                    caption=text
                )
        else:
            sent_reply = await client.send_message(
                target_group,
                text,
                reply_to=reply_to_msg_id
            )

        message_id_mapping[message.id] = sent_reply.id
    except Exception as e:
        msg = await error_handle(e)
        logger.error(f"发送回复消息失败: {msg}")


def apply_replacements(text: str) -> str:
    if not text:
        return text
    for k, v in Config.REPLACEMENTS.items():
        text = text.replace(k, v)
    return text


async def init_monitor() -> bool:
    if not globals.monitor_client:
        logger.warning(f"启动监听失败")
        return True

    await check_and_join_source(globals.monitor_client)
    logger.info("开始监听新消息")

    sessions_pool["monitor"].update({"status": "监听中"})

    @globals.monitor_client.on(events.NewMessage(chats=Config.SOURCE_GROUPS))
    async def handler(event: Message):
        try:
            await message_queue.put(event)
        except Exception as e:
            logger.error(f"入队消息时出错: {e}")

    asyncio.create_task(message_consumer())

    return True


async def message_consumer():
    while True:
        event = await message_queue.get()
        try:
            await clone_and_forward_message(event)
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
        finally:
            message_queue.task_done()

        await asyncio.sleep(1)


async def start() -> None:
    await globals.monitor_client.run_until_disconnected()


async def cease() -> bool:
    await globals.monitor_client.disconnect()
    sessions_pool["monitor"].update({"status": "离线"})
    logger.info(f"停止监听，监听账号已离线")
    return True
