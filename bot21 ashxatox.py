"""
Телеграм-бот: игра «21» для групп.

Правила: игроки по кругу называют числа от 1 до 21. За ход можно назвать
следующее число или поднять максимум на 3 (было 1 -> можно 2, 3 или 4).
Кто назвал 21 — отвечает на вопрос (есть обычные и 18+).

Запуск:
    pip install aiogram
    BOT_TOKEN=... python bot21.py
"""
import asyncio
import html
import json
import logging
import os
import random
from dataclasses import dataclass, field

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.filters import JOIN_TRANSITION, Command, CommandStart, ChatMemberUpdatedFilter
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    CallbackQuery,
    ChatMemberUpdated,
    MenuButtonCommands,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

TARGET = 21
MAX_STEP = 3
TURN_TIMEOUT = 60  # секунд на ход
MAX_PLAYERS = 20
SETTINGS_FILE = "settings.json"

router = Router()

# ----------------------------------------------------------------------------
# Вопросы и задания (добавляйте свои сколько угодно, по одному в строке)
# ----------------------------------------------------------------------------
QUESTIONS = [
    "Какая самая странная вещь есть у тебя дома, о которой никто не знает?",
    "Что ты натворил(а) такого, о чём до сих пор боишься рассказать родителям?",
    "Если бы завтра ты проснулся(ась) в теле человека из этого чата — кого бы выбрал(а) и что сделал(а) бы первым делом?",
    "Какая твоя самая большая ложь, которую так и не раскрыли?",
    "Кого из этой компании ты взял(а) бы в напарники в зомби-апокалипсисе, а кого оставил(а) бы первым?",
    "Какой самый дурацкий поступок ты совершил(а) ради лайков или внимания?",
    "Что ты удалил(а) из телефона перед тем, как кому-то его отдать?",
    "Какое прозвище у тебя было в детстве, о котором хочется забыть?",
    "Что в себе ты считаешь самым раздражающим?",
    "Чьё сообщение ты прочитал(а), но специально не ответил(а)? Почему?",
    "Какую песню ты слушаешь втайне, и тебе за неё стыдно?",
    "С кем из этого чата ты бы поменялся(лась) жизнью на месяц и почему?",
    "О каком своём решении ты жалеешь больше всего?",
    "Что самое безумное ты гуглил(а) в интернете?",
    "Какой подарок ты получил(а) и сразу перепродал(а) или выбросил(а)?",
    "Кто в этой компании самый вредный и почему?",
    "Что бы ты сделал(а), если бы нашёл(ла) чужой кошелёк с огромной суммой?",
    "Какой у тебя был самый ужасный экзамен или собеседование?",
    "Какое твоё самое неловкое сообщение «не тому человеку»?",
    "Какую суперспособность ты бы выбрал(а) и как использовал(а) бы её не по назначению?",
    "Что тебе нравится в себе, а другие этого не замечают?",
    "Ты когда-нибудь списывал(а) на экзамене? Расскажи, как.",
    "Какую вещь ты берёшь у друзей и не возвращаешь?",
    "Назови человека из чата, которому ты доверишь любую тайну, и того, кому нет.",
    "Какой самый большой ляп у тебя был при знакомстве с новым человеком?",
    "У тебя миллион, но потратить его нужно за сутки. На что?",
    "Какая у тебя самая странная фобия или суеверие?",
    "Что тебя больше всего бесит в этом чате?",
    "Какую вредную привычку ты никак не можешь бросить?",
    "Над каким фильмом или видео ты последний раз плакал(а)?",
    "Какой комплимент ты хочешь услышать, но никто не говорит?",
    "Кому из чата ты сделал(а) бы татуировку на спор — и какую?",
    "Как назывался бы фильм о твоей жизни и кто сыграл бы тебя?",
    "Что бы ты сказал(а) себе пятилетней давности?",
    "Какой самый глупый спор на деньги или на желание у тебя был?",
    "Какую самую позорную историю из школы ты помнишь?",
    "Что ты ел(а) такого, что другим показалось бы отвратительным?",
    "Какой самый странный подарок ты дарил(а)?",
    "Кого из чата ты взял(а) бы в команду для ограбления банка и какие роли распределил(а) бы?",
    "Какой у тебя есть талант, о котором почти никто не знает?",
    "Расскажи про самый нелепый случай с тобой на людях.",
    "Что ты скрываешь от друзей из-за страха быть осмеянным?",
    "Какие три вещи ты взял(а) бы на необитаемый остров?",
    "Чьи мысли из чата ты хотел(а) бы читать сутки?",
    "Что ты гуглил(а) последним? Говори честно.",
    "Какой у тебя самый странный вкус в еде?",
    "Какой самый безумный поступок ты хочешь совершить до 30 лет?",
    "Кого из присутствующих ты считаешь самым непредсказуемым?",
    "Какой лайфхак ты придумал(а), но стыдишься применять?",
    "Что бы ты сделал(а), если бы стал(а) президентом на один день?",
    "Какой день из жизни ты хотел(а) бы пережить заново?",
    "Что тебе сложнее всего простить?",
    "Расскажи самую смешную историю про друзей из этого чата.",
    "В чём ты приукрасил(а) правду в соцсетях или резюме?",
    "Какую часть своей внешности ты любишь больше всего?",
    "Если бы у тебя был секретный аккаунт — чем бы он занимался?",
    "Какая неожиданная мелочь выводит тебя из себя?",
    "Какую самую большую глупость ты совершил(а) за деньги?",
    "Если бы тебе пришлось выбрать одного человека из чата для совместного путешествия на месяц — кого?",
    "Что ты сделал(а) бы, если бы никто и никогда об этом не узнал?",
    # задания
    "ЗАДАНИЕ: отправь в чат последнее фото из галереи (если не стыдно) или расскажи, что на нём.",
    "ЗАДАНИЕ: изобрази любого человека из чата, остальные угадывают кого.",
    "ЗАДАНИЕ: придумай прозвище каждому игроку и объясни его.",
    "ЗАДАНИЕ: расскажи историю из своей жизни, в которой нужно соврать в одном месте. Остальные ищут ложь.",
    "ЗАДАНИЕ: напиши в чат голосовое с песней, которую выберут остальные.",
    "ЗАДАНИЕ: покажи свой лучший танцевальный элемент голосом в сообщении (опиши словами).",
    "ЗАДАНИЕ: поменяй аватарку на любую смешную по выбору чата на час.",
    "ЗАДАНИЕ: сделай комплимент каждому игроку по очереди.",
]

ADULT_QUESTIONS = [
    "Кого из этого чата ты бы поцеловал(а), если бы пришлось выбрать?",
    "Какой самый смелый поступок ты совершил(а) ради симпатии?",
    "Самое странное место, где ты целовался(ась)?",
    "Какую «красную линию» в отношениях ты не переступишь никогда?",
    "Расскажи о самом неловком свидании в твоей жизни.",
    "Что в людях привлекает тебя сильнее всего с первого взгляда?",
    "Ты когда-нибудь влюблялся(ась) в человека из этого чата?",
    "Какой самый странный подкат ты слышал(а)?",
    "Ты писал(а) бывшему(ей) среди ночи? Чем всё закончилось?",
    "Какой твой главный «ред флаг» в отношениях?",
    "С кем из чата ты ни за что не стал(а) бы встречаться и почему?",
    "Что тебя заводит в человеке сильнее всего: ум, юмор или внешность?",
    "Какой лучший флирт был в твоей жизни? Расскажи, как это было.",
    "Что самое безумное ты вытворял(а) в подпитии?",
    "Кому из чата ты написал(а) бы «скучаю», если бы это не имело последствий?",
    "У тебя была любовь с первого взгляда? Чем всё закончилось?",
    "Какое самое странное расставание у тебя было?",
    "Что бы ты не простил(а) партнёру: измену, ложь или грубость?",
    "Какое самое смелое сообщение ты отправлял(а) тому, кто нравится?",
    "Кого из чата ты выбрал(а) бы для романтического ужина при свечах?",
    "Что ты делаешь, чтобы понравиться человеку?",
    "Каким был твой первый поцелуй? Оценка по 10-балльной шкале.",
    "Ты хранишь переписку с бывшим(ей)? Почему?",
    "Как выглядит свидание твоей мечты?",
    "По каким признакам ты понимаешь, что человек тебе нравится?",
    "Кто из чата, по-твоему, самый(ая) флиртующий(ая)?",
    "Что ты скажешь бывшему(ей), если встретишь его(её) сегодня?",
    "Какая самая пикантная переписка у тебя была? Без подробностей.",
    "Что для тебя «слишком» на первом свидании?",
    "Каким должен быть идеальный поцелуй?",
    "Чьё внимание ты хотел(а) получить, но не получил(а)?",
    "Кто из чата самый(ая) обаятельный(ая) и почему?",
    "Какой самый безумный поступок ты совершил(а) из ревности?",
    "Ты когда-нибудь встречался(ась) с двумя людьми одновременно?",
    "Что ты никогда не сделаешь на первом свидании?",
    "Если бы можно было вернуть бывшего(ую) на один день — кого и зачем?",
    "Как далеко ты готов(а) зайти ради человека, который тебе нравится?",
    "Ты в отношениях собственник(ница) или свободолюбец?",
    "Какой был твой самый романтичный (или самый горячий) момент?",
    "Сколько человек из чата, по-твоему, тайно в тебя влюблены?",
    "Какое самое откровенное признание ты слышал(а)?",
    "Что для тебя красный флаг в переписке?",
    "Ты когда-нибудь целовался(ась) с другом или подругой?",
    "Что ты думаешь об отношениях на одну ночь? Честно.",
    "Как ты отреагируешь, если партнёр проверит твой телефон?",
    "С кем из присутствующих у тебя больше всего химии?",
    "Что самое смелое ты хочешь сделать с человеком, который нравится?",
    "Какой самый большой грех в твоей жизни, о котором никто не знает?",
    "Опиши свой идеальный тип внешности и характера. Кто в чате ближе всего?",
    "Какая у тебя самая безумная фантазия на путешествие вдвоём?",
    # задания 18+
    "ЗАДАНИЕ: напиши голосовое с признанием в любви кому-то из чата (в шутку).",
    "ЗАДАНИЕ: отправь последнему человеку, с кем ты целовался(ась), «привет, как дела?» (если решишься).",
    "ЗАДАНИЕ: выбери игрока и пошли ему самый смелый комплимент.",
    "ЗАДАНИЕ: расскажи самый пикантный секрет, который можно озвучить на публику.",
    "ЗАДАНИЕ: оставшиеся игроки голосуют, кто из них самый(ая) опасный(ая) соблазнитель(ница). Назови причины.",
    "ЗАДАНИЕ: сделай глоток напитка и расскажи самую смешную историю про свидание.",
    "ЗАДАНИЕ: придумай подкат для любого игрока из чата и произнеси его.",
]

# «мешки»: вопросы выпадают без повторов, пока не закончится весь список
_bags: dict[tuple, list] = {}


def pick_question(chat_id: int) -> str:
    adult = adult_enabled(chat_id)
    key = (chat_id, adult)
    if not _bags.get(key):
        pool = QUESTIONS + (ADULT_QUESTIONS if adult else [])
        random.shuffle(pool)
        _bags[key] = pool
    return _bags[key].pop()


# ----------------------------------------------------------------------------
# Настройки чатов и рейтинг
# ----------------------------------------------------------------------------
def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings() -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False)


settings: dict = load_settings()


def adult_enabled(chat_id: int) -> bool:
    return bool(settings.get(str(chat_id), {}).get("adult", False))


def add_loss(chat_id: int, uid: int, name: str) -> None:
    cfg = settings.setdefault(str(chat_id), {})
    entry = cfg.setdefault("stats", {}).setdefault(str(uid), {"name": name, "lost": 0})
    entry["name"] = name
    entry["lost"] += 1
    save_settings()


# ----------------------------------------------------------------------------
# Состояние игры
# ----------------------------------------------------------------------------
@dataclass
class Game:
    chat_id: int
    host_id: int
    message_id: int = 0
    players: list = field(default_factory=list)  # [(user_id, name)]
    started: bool = False
    last: int = 0
    turn: int = 0
    turn_token: int = 0
    timer: asyncio.Task | None = None


games: dict[int, Game] = {}


def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'


def players_list(g: Game) -> str:
    return "\n".join(f"{i}. {mention(uid, n)}" for i, (uid, n) in enumerate(g.players, 1))


def lobby_text(g: Game) -> str:
    return (
        f"🎲 <b>Игра «21»</b>\n\n"
        f"Называем числа по кругу. За ход можно назвать следующее число "
        f"или поднять максимум на {MAX_STEP}. Кто назвал <b>{TARGET}</b> — "
        f"отвечает на вопрос!\n\n"
        f"Режим 18+: {'включён 🔞' if adult_enabled(g.chat_id) else 'выключен'}\n\n"
        f"<b>Игроки ({len(g.players)}):</b>\n{players_list(g)}"
    )


def lobby_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✋ Вступить", callback_data="join")
    kb.button(text="🚪 Выйти", callback_data="leave")
    kb.button(text="▶️ Начать", callback_data="begin")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(2, 2)
    return kb.as_markup()


def turn_text(g: Game) -> str:
    uid, name = g.players[g.turn]
    lo = g.last + 1
    hi = min(g.last + MAX_STEP, TARGET)
    return (
        f"🔢 Последнее число: <b>{g.last}</b>\n"
        f"Ходит: {mention(uid, name)}\n"
        f"Можно назвать от <b>{lo}</b> до <b>{hi}</b> · ⏱ {TURN_TIMEOUT} сек"
    )


def turn_kb(g: Game):
    kb = InlineKeyboardBuilder()
    for n in range(g.last + 1, min(g.last + MAX_STEP, TARGET) + 1):
        kb.button(text=str(n), callback_data=f"num:{n}")
    kb.adjust(MAX_STEP)
    return kb.as_markup()


async def send_turn(bot: Bot, g: Game) -> None:
    """Каждый ход — НОВОЕ сообщение, чтобы его было видно внизу чата."""
    msg = await bot.send_message(g.chat_id, turn_text(g), reply_markup=turn_kb(g))
    g.message_id = msg.message_id
    start_timer(bot, g)


def cancel_timer(g: Game) -> None:
    if g.timer and not g.timer.done():
        g.timer.cancel()
    g.timer = None


def start_timer(bot: Bot, g: Game) -> None:
    cancel_timer(g)
    g.turn_token += 1
    g.timer = asyncio.create_task(turn_timeout(bot, g, g.turn_token))


async def turn_timeout(bot: Bot, g: Game, token: int) -> None:
    try:
        await asyncio.sleep(TURN_TIMEOUT)
    except asyncio.CancelledError:
        return
    if games.get(g.chat_id) is not g or g.turn_token != token:
        return
    uid, name = g.players[g.turn]
    await finish(bot, g, uid, name, f"⌛ {mention(uid, name)} не успел(а) сходить.")


async def remove_keyboard(bot: Bot, g: Game) -> None:
    try:
        await bot.edit_message_reply_markup(g.chat_id, g.message_id, reply_markup=None)
    except Exception:
        pass


async def finish(bot: Bot, g: Game, uid: int, name: str, reason: str) -> None:
    cancel_timer(g)
    games.pop(g.chat_id, None)
    add_loss(g.chat_id, uid, name)
    q = pick_question(g.chat_id)
    await remove_keyboard(bot, g)
    await bot.send_message(
        g.chat_id,
        f"{reason}\n\n🎯 Отвечает {mention(uid, name)}:\n\n<b>{html.escape(q)}</b>\n\n"
        f"Ещё раз: /newgame",
    )


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    m = await bot.get_chat_member(chat_id, user_id)
    return m.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)


# ----------------------------------------------------------------------------
# Команды
# ----------------------------------------------------------------------------
RULES = (
    "🎲 <b>Игра «21»</b>\n\n"
    "Игроки по очереди называют числа. За ход можно назвать следующее число "
    f"или поднять максимум на {MAX_STEP} (сказали 1 — можно 2, 3 или 4). "
    f"Кто назвал <b>{TARGET}</b> — отвечает на вопрос или выполняет задание "
    "(есть и 18+).\n\n"
    "<b>Команды (в группе):</b>\n"
    "/newgame — новая игра\n"
    "/stop — остановить игру (может любой участник)\n"
    "/question — случайный вопрос\n"
    "/rating — рейтинг чата\n"
    "/mode18 — вкл/выкл вопросы 18+ (только админы)\n"
    "/rules — правила"
)

GROUP_COMMANDS = [
    BotCommand(command="newgame", description="Новая игра"),
    BotCommand(command="stop", description="Остановить игру"),
    BotCommand(command="question", description="Случайный вопрос"),
    BotCommand(command="rating", description="Показать рейтинг чата"),
    BotCommand(command="mode18", description="Включить/выключить 18+"),
    BotCommand(command="rules", description="Показать правила игры"),
]
PRIVATE_COMMANDS = [
    BotCommand(command="start", description="Как играть"),
    BotCommand(command="rules", description="Показать правила игры"),
]


@router.message(CommandStart())
@router.message(Command("rules", "help"))
async def cmd_start(m: Message, bot: Bot):
    text = RULES
    if m.chat.type == ChatType.PRIVATE:
        me = await bot.get_me()
        text += f"\n\n➕ Добавь меня в группу: https://t.me/{me.username}?startgroup=true"
    await m.answer(text)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_added(event: ChatMemberUpdated, bot: Bot):
    if event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await bot.send_message(
            event.chat.id,
            "👋 Всем привет! Я бот для игры «21».\n"
            "Напишите /newgame, чтобы начать, или /rules — правила.\n\n"
            "💡 Чтобы кнопки и команды работали стабильно, лучше сделать меня админом.",
        )


def in_group(m: Message) -> bool:
    return m.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


@router.message(Command("newgame"))
async def cmd_newgame(m: Message):
    if not in_group(m):
        await m.answer("Игра работает только в группах. Добавь меня в группу и напиши /newgame 🙂")
        return
    if m.chat.id in games:
        await m.reply("В этом чате уже идёт игра. Остановить: /stop")
        return
    g = Game(chat_id=m.chat.id, host_id=m.from_user.id)
    g.players.append((m.from_user.id, m.from_user.full_name))
    sent = await m.answer(lobby_text(g), reply_markup=lobby_kb())
    g.message_id = sent.message_id
    games[m.chat.id] = g


@router.message(Command("stop"))
async def cmd_stop(m: Message, bot: Bot):
    g = games.get(m.chat.id)
    if not g:
        await m.reply("Сейчас нет активной игры.")
        return
    cancel_timer(g)
    games.pop(m.chat.id, None)
    await remove_keyboard(bot, g)
    await m.answer(f"🛑 {mention(m.from_user.id, m.from_user.full_name)} остановил(а) игру.")


@router.message(Command("question"))
async def cmd_question(m: Message):
    await m.answer(f"❓ <b>{html.escape(pick_question(m.chat.id))}</b>")


@router.message(Command("rating"))
async def cmd_rating(m: Message):
    stats = settings.get(str(m.chat.id), {}).get("stats", {})
    if not stats:
        await m.answer("Рейтинг пока пуст. Сыграйте в /newgame!")
        return
    top = sorted(stats.values(), key=lambda e: e["lost"], reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else str(i + 1) + '.'} {html.escape(e['name'])} — {e['lost']}"
        for i, e in enumerate(top)
    ]
    await m.answer("🏆 <b>Кто чаще всех называл 21 (отвечал на вопросы):</b>\n\n" + "\n".join(lines))


@router.message(Command("mode18"))
async def cmd_mode18(m: Message, bot: Bot):
    if not in_group(m):
        await m.answer("Эта команда работает в группе.")
        return
    if not await is_admin(bot, m.chat.id, m.from_user.id):
        await m.reply("Переключать режим 18+ могут только админы.")
        return
    cfg = settings.setdefault(str(m.chat.id), {})
    cfg["adult"] = not cfg.get("adult", False)
    save_settings()
    _bags.clear()
    await m.answer(
        "🔞 Режим 18+ <b>включён</b>: в вопросах появятся пикантные." if cfg["adult"]
        else "✅ Режим 18+ <b>выключен</b>."
    )


# ----------------------------------------------------------------------------
# Кнопки
# ----------------------------------------------------------------------------
@router.callback_query(F.data == "join")
async def cb_join(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await c.answer("Набор в игру закрыт.", show_alert=True)
        return
    if any(uid == c.from_user.id for uid, _ in g.players):
        await c.answer("Ты уже в игре!")
        return
    if len(g.players) >= MAX_PLAYERS:
        await c.answer("Игра заполнена.", show_alert=True)
        return
    g.players.append((c.from_user.id, c.from_user.full_name))
    await c.message.edit_text(lobby_text(g), reply_markup=lobby_kb())
    await c.answer("Ты в игре!")


@router.callback_query(F.data == "leave")
async def cb_leave(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await c.answer()
        return
    g.players = [(u, n) for u, n in g.players if u != c.from_user.id]
    if not g.players:
        games.pop(g.chat_id, None)
        await c.message.edit_text("Все вышли, игра отменена.")
        await c.answer()
        return
    if g.host_id == c.from_user.id:
        g.host_id = g.players[0][0]
    await c.message.edit_text(lobby_text(g), reply_markup=lobby_kb())
    await c.answer("Ты вышел(а).")


@router.callback_query(F.data == "cancel")
async def cb_cancel(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await c.answer()
        return
    games.pop(g.chat_id, None)  # отменить может любой участник чата
    await c.message.edit_text(
        f"❌ {mention(c.from_user.id, c.from_user.full_name)} отменил(а) игру."
    )
    await c.answer()


@router.callback_query(F.data == "begin")
async def cb_begin(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await c.answer()
        return
    if c.from_user.id != g.host_id:
        await c.answer("Начать может только создатель игры.", show_alert=True)
        return
    if len(g.players) < 2:
        await c.answer("Нужно минимум 2 игрока!", show_alert=True)
        return
    random.shuffle(g.players)
    g.started = True
    g.last = 0
    g.turn = 0
    await c.message.edit_text(
        f"🎲 <b>Игра «21» началась!</b>\n\n<b>Порядок ходов:</b>\n{players_list(g)}",
        reply_markup=None,
    )
    await c.answer("Поехали!")
    await send_turn(bot, g)


@router.callback_query(F.data.startswith("num:"))
async def cb_number(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    if not g or not g.started:
        await c.answer("Игра уже закончилась.", show_alert=True)
        return
    uid, name = g.players[g.turn]
    if c.from_user.id != uid:
        await c.answer("Сейчас не твой ход!", show_alert=True)
        return
    if c.message.message_id != g.message_id:
        await c.answer("Это старая кнопка.", show_alert=True)
        return
    n = int(c.data.split(":")[1])
    if not (g.last + 1 <= n <= min(g.last + MAX_STEP, TARGET)):
        await c.answer("Так нельзя.", show_alert=True)
        return

    # сначала меняем состояние (без await), чтобы двойной клик не прошёл дважды
    g.last = n
    await c.answer(f"Ты назвал(а) {n}")

    if n >= TARGET:
        await finish(bot, g, uid, name, f"💥 {mention(uid, name)} назвал(а) <b>{TARGET}</b>!")
        return

    g.turn = (g.turn + 1) % len(g.players)
    cancel_timer(g)
    # старое сообщение остаётся в истории с результатом хода, без кнопок
    await c.message.edit_text(f"✅ {mention(uid, name)} назвал(а) <b>{n}</b>", reply_markup=None)
    await send_turn(bot, g)


# ----------------------------------------------------------------------------
async def start_web():
    """Мини-сервер, чтобы бесплатные хостинги (Render) считали сервис живым."""
    app = web.Application()

    async def ok(_):
        return web.Response(text="OK")

    app.router.add_get("/", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()


async def setup_commands(bot: Bot) -> None:
    """Меню команд (кнопка «/» в Telegram) с описаниями."""
    try:
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeDefault())
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        saved = await bot.get_my_commands(scope=BotCommandScopeAllGroupChats())
        print(f"✅ Меню команд установлено ({len(saved)} шт.): "
              + ", ".join("/" + c.command for c in saved))
    except Exception as e:
        print(f"❌ Не удалось установить меню команд: {e}")
        logging.exception("Не удалось установить меню команд")


async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Укажи токен: export BOT_TOKEN=...")
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
