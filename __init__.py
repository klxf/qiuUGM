from configs.config import Config
from configs.path_config import DATA_PATH
from nonebot.adapters.onebot.v11.permission import GROUP
from nonebot import on_command, on_notice, on_regex, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, GroupIncreaseNoticeEvent
from services.log import logger
from utils.image_utils import text2image
from utils.message_builder import image
import json
import re
import aiohttp, asyncio
from typing import Tuple, Dict, Any

__zx_plugin_name__ = "联合群管"
__plugin_usage__ = """
usage：
    ........
""".strip()
__plugin_des__ = "qiuUGM"
__plugin_cmd__ = ["/封禁", "/解封", "/警告", "/查", "/UGM"]
__plugin_version__ = 0.1
__plugin_author__ = "Mr_Fang"
__plugin_setting__ = {
    "level": 5,
    "default_status": True,
    "limit_superuser": False,
    "cmd": ["/封禁", "/解封", "/警告", "/查", "/UGM"],
}

join_group_handle = on_notice(priority=1, block=False)
msg_handler = on_message(permission=GROUP, priority=5)
admin_cmd_ban = on_regex(r"/封禁", priority=5, block=True)
admin_cmd_unban = on_regex(r"/解封", priority=5, block=True)
admin_cmd_warn = on_regex(r"/警告", priority=5, block=True)
admin_cmd_search = on_regex(r"/查", priority=5, block=True)

def getConfig() -> Dict[str, Any]:
    try:
        with open(DATA_PATH / "qiuUGM" / "config.json", "r", encoding="utf8") as f:
            data = json.load(f)
    except (ValueError, FileNotFoundError):
        data = {}
    return data


def getUnionBanData() -> Dict[Any, Any]:
    try:
        with open(DATA_PATH / "qiuUGM" / "unionban.json", "r", encoding="utf8") as f:
            data = json.load(f)
    except (ValueError, FileNotFoundError):
        data = {}
    return data


def getBlackWordsData() -> Dict[Any, Any]:
    try:
        with open(DATA_PATH / "qiuUGM" / "blackwords.json", "r", encoding="utf8") as f:
            data = json.load(f)
    except (ValueError, FileNotFoundError):
        data = {}
    return data


def getWarningData() -> Dict[Any, Any]:
    try:
        with open(DATA_PATH / "qiuUGM" / "warning.json", "r", encoding="utf8") as f:
            data = json.load(f)
    except (ValueError, FileNotFoundError):
        data = {}
    return data


def save_data():
    global unionBanData, warningData
    with open(DATA_PATH / "qiuUGM" / "unionban.json", "w", encoding="utf8") as f:
        json.dump(unionBanData, f, indent=4)
    with open(DATA_PATH / "qiuUGM" / "warning.json", "w", encoding="utf8") as f:
        json.dump(warningData, f, indent=4)


async def sendMsg2Admin(bot, msg):
    await bot.send_group_msg(group_id=ADMIN_GROUP, message=msg)

async def fetch_url(session, url):
    async with session.get(url) as response:
        return await response.json()


async def process_links(bot, event, match):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for link in match:
            url = base_url + link
            tasks.append(fetch_url(session, url))
        responses = await asyncio.gather(*tasks)
        for res_json in responses:
            if res_json["rating_index"] == 3:
                if event.user_id not in warningData:
                    warningData[event.user_id] = 1
                else:
                    warningData[event.user_id] += 1
                save_data()
                msg = f"""
你发送了违规图片，已被警告 {warningData[event.user_id]} 次
你将被禁止发言 {5*warningData[event.user_id]} 分钟

你所发送的内容已留档，若有异议可私聊管理人员申述
""".strip()
                await bot.delete_msg(message_id=event.message_id)
                await bot.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=5*60*warningData[event.user_id])
                await msg_handler.send(msg, at_sender=True)
                admin_msg = f"""
{event.user_id} 发送了违规图片，目前已被警告 {warningData[event.user_id]} 次
发送的违规内容：
{event.raw_message}
""".strip()
                msg_list = {
                    "type": "node",
                    "data": {
                        "name": f"sender",
                        "uin": f"{event.user_id}",
                        "content": admin_msg,
                    },
                }
                await bot.send_group_forward_msg(group_id=ADMIN_GROUP, messages=msg_list)
                # await sendMsg2Admin(bot, admin_msg)
                return


unionBanData = getUnionBanData()
warningData = getWarningData()
config = getConfig()
API_URL = config["API_URL"]
API_KEY = config["API_KEY"]
ADMIN_GROUP = config["ADMIN_GROUP"]
base_url = str(API_URL) + "/?key=" + str(API_KEY) + "&url="


@join_group_handle.handle()
async def _(bot: Bot, event: GroupIncreaseNoticeEvent):
    if str(event.user_id) not in unionBanData:
        return
    else:
        msg = f"""
{event.user_id} 已被联合封禁，自动踢出群聊。
若需解封请在群管群内使用 /解封 命令
""".strip()
        await bot.set_group_kick(group_id=event.group_id, user_id=event.user_id)
        await join_group_handle.send(msg)


@msg_handler.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    pattern = r'https://gchat\.qpic\.cn/gchatpic_new/\d+/\d+-\d+-[0-9A-F]+/0'
    match = re.findall(pattern, event.raw_message)
    await process_links(bot, event, match)


@admin_cmd_ban.handle()
async def _(event: GroupMessageEvent):
    if event.group_id != ADMIN_GROUP:
        return
    pattern = re.compile(r"/封禁 (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /封禁 <QQ>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    if match.group(1) in unionBanData:
        msg = "此号码已经被 " + str(unionBanData[match.group(1)]) + " 联合封禁"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    unionBanData[match.group(1)] = event.user_id
    save_data()
    msg = match.group(1) + "已联合封禁"
    await admin_cmd_ban.send(msg, at_sender=True)


@admin_cmd_unban.handle()
async def _(event: GroupMessageEvent):
    if event.group_id != ADMIN_GROUP:
        return
    pattern = re.compile(r"/解封 (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /解封 <QQ>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    if match.group(1) not in unionBanData:
        msg = "此号码未被联合封禁，无需解封"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    unionBanData.pop(match.group(1))
    save_data()
    msg = match.group(1) + "已解除联合封禁"
    await admin_cmd_ban.send(msg, at_sender=True)


@admin_cmd_warn.handle()
async def _(event: GroupMessageEvent):
    if event.group_id != ADMIN_GROUP:
        return
    pattern = re.compile(r"/警告 (\d+) (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /警告 <QQ> <次数>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    warningData[match.group(1)] = match.group(2)
    save_data()
    msg = match.group(1) + " 已被警告 " + match.group(2) + " 次"
    await admin_cmd_ban.send(msg, at_sender=True)


@admin_cmd_search.handle()
async def _(event: GroupMessageEvent):
    if event.group_id != ADMIN_GROUP:
        return
    pattern = re.compile(r"/查 (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /查 <QQ>"
        await admin_cmd_ban.send(msg, at_sender=True)
        # await admin_cmd_ban.send(image(b64=(await text2image(msg, color="red", padding=10)).pic2bs4()))
        return
    if match.group(1) not in unionBanData:
        ban_tip = "此号码未被联合封禁"
    else:
        ban_tip = "此号码已被 " + str(unionBanData[match.group(1)]) + " 联合封禁"
    if match.group(1) not in warningData:
        warning_tip = "此号码未被警告"
    else:
        warning_tip = "此号码已被警告 " + str(warningData[match.group(1)]) + " 次"
    msg = f"""
{ban_tip}
{warning_tip}
""".strip()
    logger.error(msg)
    await admin_cmd_ban.send(msg, at_sender=True)
