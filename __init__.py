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
__plugin_cmd__ = ["/封禁", "/解封", "/警告", "/查", "/禁言", "/踢出", "/UGM"]
__plugin_version__ = 0.3
__plugin_author__ = "Mr_Fang"
__plugin_setting__ = {
    "level": 5,
    "default_status": True,
    "limit_superuser": False,
    "cmd": __plugin_cmd__,
}

join_group_handle = on_notice(priority=1, block=False)
msg_handler = on_message(permission=GROUP, priority=5)
admin_cmd_ban = on_regex(r"/封禁", priority=5, block=True)
admin_cmd_unban = on_regex(r"/解封", priority=5, block=True)
admin_cmd_warn = on_regex(r"/警告", priority=5, block=True)
admin_cmd_search = on_regex(r"/查", priority=5, block=True)
admin_cmd_mute = on_regex(r"/禁言", priority=5, block=True)
admin_cmd_kick = on_regex(r"/踢出", priority=5, block=True)
admin_cmd_main = on_regex(r"/UGM", priority=5, block=True)

def loadConfig():
    global unionBanData, warningData, blackWords, config, ADULT_API_URL, OCR_API_URL, API_KEY, GROUP_SETTINGS, ADMIN_GROUP, FLAG, adult_base_url, ocr_base_url
    unionBanData = getUnionBanData()
    warningData = getWarningData()
    blackWords = getBlackWordsData()
    config = getConfig()
    ADULT_API_URL = config["ADULT_API_URL"]
    OCR_API_URL = config["OCR_API_URL"]
    API_KEY = config["API_KEY"]
    GROUP_SETTINGS = config["GROUP_SETTINGS"]
    ADMIN_GROUP = config["ADMIN_GROUP"]
    FLAG = config["FLAG"]
    adult_base_url = str(ADULT_API_URL) + "/?key=" + str(API_KEY) + "&url="
    ocr_base_url = str(OCR_API_URL) + "/?key=" + str(API_KEY) + "&url="

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


def debugLogger(msg):
    if FLAG['DEBUG']:
        logger.info(msg)


async def sendMsg2Admin(bot, group, msg):
    if FLAG['FORWARD'] is False:
        return
    if FLAG['TXT2IMG']:
        msg = image(b64=(await text2image(msg, color="white", padding=10)).pic2bs4())
    await bot.send_group_msg(group_id=GROUP_SETTINGS[str(group)], message=msg)


async def sendMsg2User(bot, group, msg):
    if FLAG['REMIND'] is False:
        return
    if FLAG['TXT2IMG']:
        msg = image(b64=(await text2image(msg, color="white", padding=10)).pic2bs4())
    await bot.send_group_msg(group_id=group, message=msg)


def checkBlackWords(msg: str):
    debugLogger(f"Checking black words in {msg}")
    for type in blackWords:
        pattern = re.compile(blackWords[type])
        match = pattern.search(msg)
        if match:
            return type
    return None


async def fetch_url(session, url):
    async with session.get(url) as response:
        try:
            return await response.json()
        except json.decoder.JSONDecodeError:
            return {
                "base64": "",
                "result": [
                    {
                        "save_path": "",
                        "data": []
                    }
                ]
            }


async def process_links(bot, event, match):
    async with aiohttp.ClientSession() as session:
        atasks = []
        for link in match:
            url = adult_base_url + link
            atasks.append(fetch_url(session, url))
        adult_responses = await asyncio.gather(*atasks)
        btasks = []
        for link in match:
            url = ocr_base_url + link
            btasks.append(fetch_url(session, url))
        ocr_responses = await asyncio.gather(*btasks)
        for res_json in adult_responses:
            debugLogger(f"Adult result: {res_json}")
            if res_json["rating_index"] == 3:
                if str(event.user_id) not in warningData:
                    warningData[str(event.user_id)] = 1
                else:
                    warningData[str(event.user_id)] += 1
                save_data()

                logger.info(f"{event.user_id} 在 {event.group_id} 发送了评级 {res_json['rating_index']} 的图片，目前已被警告 {warningData[str(event.user_id)]} 次")

                # 撤回
                await bot.delete_msg(message_id=event.message_id)

                # 禁言
                if FLAG['MUTE']:
                    await bot.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=5*60*warningData[str(event.user_id)])

                # 提醒
                msg = f"""
你发送了违规图片，已被警告 {warningData[str(event.user_id)]} 次
你将被禁止发言 {5 * warningData[str(event.user_id)]} 分钟

你所发送的内容已留档，若有异议可私聊管理人员申述
""".strip()
                await sendMsg2User(bot, event.group_id, msg)

                # 管理员提醒
                admin_msg = f"""
{event.user_id} 在 {event.group_id} 发送了违规图片，目前已被警告 {warningData[str(event.user_id)]} 次

发送的违规内容：
{event.raw_message}
""".strip()
                await sendMsg2Admin(bot, GROUP_SETTINGS[str(event.group_id)], admin_msg)

        for res_json in ocr_responses:
            data = res_json["result"][0]["data"]
            debugLogger(f"OCR result: {data}")
            blackWordType = checkBlackWords(str(data))
            if blackWordType is not None:
                if str(event.user_id) not in warningData:
                    warningData[str(event.user_id)] = 1
                else:
                    warningData[str(event.user_id)] += 1
                save_data()

                logger.info(f"{event.user_id} 在 {event.group_id} 发送了包含 {blackWordType} 类违规的消息，目前已被警告 {warningData[str(event.user_id)]} 次")

                # 撤回
                await bot.delete_msg(message_id=event.message_id)

                # 禁言
                if FLAG['MUTE']:
                    await bot.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=5*60*warningData[str(event.user_id)])

                # 提醒
                msg = f"""
你发送了{blackWordType}违规内容，已被警告 {warningData[str(event.user_id)]} 次
你将被禁止发言 {5 * warningData[str(event.user_id)]} 分钟
""".strip()
                await sendMsg2User(bot, event.group_id, msg)

                # 管理员提醒
                admin_msg = f"""
{event.user_id} 在 {event.group_id} 发送了包含 {blackWordType} 类违规的消息，目前已被警告 {warningData[str(event.user_id)]} 次

违规内容：
{event.raw_message}
""".strip()
                await sendMsg2Admin(bot, event.group_id, admin_msg)


# 加载配置
loadConfig()


@join_group_handle.handle()
async def _(bot: Bot, event: GroupIncreaseNoticeEvent):
    if str(event.group_id) not in GROUP_SETTINGS:
        return

    if str(event.user_id) not in unionBanData:
        return
    else:
        # 踢出
        await bot.set_group_kick(group_id=event.group_id, user_id=event.user_id)

        # 提醒
        msg = f"""
{event.user_id} 已被联合封禁，自动踢出群聊。
若需解封请在群管群内使用 /解封 命令
""".strip()
        await sendMsg2User(bot, event.group_id, msg)

        # 管理员提醒
        admin_msg = f"""
{event.user_id} 尝试加入 {event.group_id}，已踢出
若需解封请在使用 /解封 命令
""".strip()
        await sendMsg2Admin(bot, event.group_id, admin_msg)


@msg_handler.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if str(event.group_id) in GROUP_SETTINGS:
        img_pattern = r'https://gchat\.qpic\.cn/gchatpic_new/\d+/\d+-\d+-[0-9A-F]+/0'
        img_match = re.findall(img_pattern, event.raw_message)
        if img_match:
            await process_links(bot, event, img_match)

        blackWordType = checkBlackWords(event.raw_message)
        if blackWordType is not None:
            if str(event.user_id) not in warningData:
                warningData[str(event.user_id)] = 1
            else:
                warningData[str(event.user_id)] += 1
            save_data()

            logger.info(f"{event.user_id} 在 {event.group_id} 发送了包含 {blackWordType} 类违规的消息，目前已被警告 {warningData[str(event.user_id)]} 次")

            # 撤回
            await bot.delete_msg(message_id=event.message_id)

            # 禁言
            if FLAG['MUTE']:
                await bot.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=5*60*warningData[str(event.user_id)])

            # 提醒
            msg = f"""
你发送了{blackWordType}违规内容，已被警告 {warningData[str(event.user_id)]} 次
你将被禁止发言 {5 * warningData[str(event.user_id)]} 分钟
""".strip()
            await sendMsg2User(bot, event.group_id, msg)

            # 管理员提醒
            admin_msg = f"""
{event.user_id} 在 {event.group_id} 发送了包含 {blackWordType} 类违规的消息，目前已被警告 {warningData[str(event.user_id)]} 次

违规内容：
{event.raw_message}
""".strip()
            await sendMsg2Admin(bot, event.group_id, admin_msg)


@admin_cmd_ban.handle()
async def _(event: GroupMessageEvent):
    if event.group_id not in ADMIN_GROUP:
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
    if event.group_id not in ADMIN_GROUP:
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
    if event.group_id not in ADMIN_GROUP:
        return
    pattern = re.compile(r"/警告 (\d+) (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /警告 <QQ> <次数>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    warningData[match.group(1)] = int(match.group(2))
    save_data()
    msg = match.group(1) + " 已被警告 " + match.group(2) + " 次"
    await admin_cmd_ban.send(msg, at_sender=True)


@admin_cmd_search.handle()
async def _(event: GroupMessageEvent):
    if event.group_id not in ADMIN_GROUP:
        return
    pattern = re.compile(r"/查 (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /查 <QQ>"
        await admin_cmd_ban.send(msg, at_sender=True)
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
    await admin_cmd_ban.send(msg, at_sender=True)


@admin_cmd_mute.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if event.group_id not in ADMIN_GROUP:
        return
    pattern = re.compile(r"/禁言 (\d+) (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /禁言 <QQ> <分钟>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    groups = [key for key, value in GROUP_SETTINGS.items() if value == event.group_id]
    for group in groups:
        for user_info in await bot.get_group_member_list(group_id=int(group)):
            if int(match.group(1)) == user_info["user_id"] and user_info["role"] == "member":
                await bot.set_group_ban(group_id=int(group), user_id=int(match.group(1)), duration=int(match.group(2)) * 60)
                break
    await admin_cmd_ban.send(f"已禁言 {match.group(1)} {match.group(2)} 分钟", at_sender=True)


@admin_cmd_kick.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    if event.group_id not in ADMIN_GROUP:
        return
    pattern = re.compile(r"/踢出 (\d+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = "格式错误，请输入 /踢出 <QQ>"
        await admin_cmd_ban.send(msg, at_sender=True)
        return
    groups = [key for key, value in GROUP_SETTINGS.items() if value == event.group_id]
    for group in groups:
        for user_info in await bot.get_group_member_list(group_id=int(group)):
            if int(match.group(1)) == user_info["user_id"] and user_info["role"] == "member":
                await bot.set_group_kick(group_id=int(group), user_id=int(match.group(1)))
                break
    await admin_cmd_ban.send(f"已踢出 {match.group(1)}", at_sender=True)


@admin_cmd_main.handle()
async def _(event: GroupMessageEvent):
    if event.group_id not in ADMIN_GROUP:
        return
    pattern = re.compile(r"/UGM (\S+)")
    match = pattern.match(event.raw_message)
    if not match:
        msg = f"""
<f font_size=24 font_color=blue>感谢使用 qiuUGM 联合群管插件</f> <f font_color=gray>v{__plugin_version__}</f>

<f font_size=22 font_color=green>== 命令列表 ==</f>
`/封禁 <QQ>` <f font_color=gray>— 封禁指定账号</f>
`/解封 <QQ>` <f font_color=gray>— 解封指定账号</f>
`/警告 <QQ> <次数>` <f font_color=gray>— 警告指定账号</f>
`/查 <QQ>` <f font_color=gray>— 查看指定账号信息</f>
`/禁言 <QQ> <分钟>` <f font_color=gray>— 禁言指定账号</f>
`/踢出 <QQ>` <f font_color=gray>— 踢出指定账号</f>
`/封禁 <QQ>` <f font_color=gray>— 封禁指定账号</f>

<f font_size=22 font_color=green>== 主命令 ==</f>
`/UGM` <f font_color=gray>— 显示此帮助</f>
`/UGM reload` <f font_color=gray>— 重新加载配置</f>
`/UGM flag` <f font_color=gray>— 查看 FLAG</f>

<f font_size=15>本插件是开源项目，遵循 GUN GPL v3.0 协议</f>
<f font_size=15>github.com/klxf/qiuUGM</f>

<f font_size=24 font_color=orange>叶秋可爱捏~</f>
        """.strip()
        msg = image(b64=(await text2image(msg, color="white", padding=10)).pic2bs4())
        await admin_cmd_ban.send(msg)
        return
    if match.group(1) == "reload":
        loadConfig()
        msg = "已重新加载配置"
        await admin_cmd_ban.send(msg, at_sender=True)
    if match.group(1) == "flag":
        msg = f"""
<f font_size=24 font_color=blue>qiuUGM FLAG</f>

修改 FLAG 请编辑配置文件
REMIND={FLAG['REMIND']}
FORWARD={FLAG['FORWARD']}
MUTE={FLAG['MUTE']}
TXT2IMG={FLAG['TXT2IMG']}
DEBUG={FLAG['DEBUG']}

<f font_size=15>本插件是开源项目，遵循 GUN GPL v3.0 协议</f>
<f font_size=15>github.com/klxf/qiuUGM</f>

<f font_size=24 font_color=orange>叶秋可爱捏~</f>
        """.strip()
        msg = image(b64=(await text2image(msg, color="white", padding=10)).pic2bs4())
        await admin_cmd_ban.send(msg)