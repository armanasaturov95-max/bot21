"""
Телеграм-бот: игра «21» для групп.

Правила: игроки по кругу называют числа. За ход можно назвать следующее число
или поднять максимум на 2/3/5. Кто назвал последнее число (21) — выбирает
«Вопрос» или «Задание». Остальные голосуют, честно ли он справился.

Запуск:
    pip install aiogram
    BOT_TOKEN=... python bot21.py
"""
import asyncio
import html
import itertools
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

# ----------------------------------------------------------------------------
# Настройки игры
# ----------------------------------------------------------------------------
TARGETS = [21, 31, 51, 15]      # варианты цели (первый — по умолчанию)
STEPS = [3, 2, 5]               # варианты максимального шага
TURN_SECONDS = 60               # обычный режим
FAST_SECONDS = 15               # быстрый режим
PICK_SECONDS = 20               # выбор цели на число 7
CHOOSE_SECONDS = 60             # выбор «Вопрос/Задание»
DOING_SECONDS = 180             # время на ответ / выполнение
VOTE_SECONDS = 30               # голосование
MAX_PLAYERS = 20
SETTINGS_FILE = "settings.json"

LUCKY = 7        # на этом числе игрок выбирает, кому задать вопрос
REVERSE = 13     # на этом числе порядок ходов разворачивается

CAT_LABEL = {
    "all": "Всё вместе",
    "fun": "Весёлые",
    "love": "Про отношения",
    "hard": "Жёсткие 18+",
}

router = Router()

# ----------------------------------------------------------------------------
# Вопросы и задания (добавляйте свои — по одному в строке, в кавычках, с запятой)
# fun — весёлые, love — про отношения, hard — жёсткие 18+ (нужен /mode18)
# ----------------------------------------------------------------------------
QUESTIONS = {
    "fun": [
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
        "Если бы у тебя был секретный аккаунт — чем бы он занимался?",
        "Какая неожиданная мелочь выводит тебя из себя?",
        "Какую самую большую глупость ты совершил(а) за деньги?",
        "Что ты сделал(а) бы, если бы никто и никогда об этом не узнал?",
        "Кто из чата первым предаст команду в «Мафии» и почему именно он?",
        "Какой твой самый большой страх на людях?",
    ],
    "love": [
        "Расскажи о самом неловком свидании в твоей жизни.",
        "Что в людях привлекает тебя сильнее всего с первого взгляда?",
        "Ты когда-нибудь влюблялся(ась) в человека из этого чата?",
        "Какой самый странный подкат ты слышал(а)?",
        "Ты писал(а) бывшему(ей) среди ночи? Чем всё закончилось?",
        "Какой твой главный «ред флаг» в отношениях?",
        "С кем из чата ты ни за что не стал(а) бы встречаться и почему?",
        "Какой лучший флирт был в твоей жизни? Расскажи, как это было.",
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
        "Что для тебя «слишком» на первом свидании?",
        "Кто из чата самый(ая) обаятельный(ая) и почему?",
        "Какой самый безумный поступок ты совершил(а) из ревности?",
        "Что для тебя красный флаг в переписке?",
        "Ты когда-нибудь дружил(а) с человеком и скрывал(а), что он(а) тебе нравится?",
        "Как ты отреагируешь, если партнёр проверит твой телефон?",
        "Какой самый романтичный поступок ты совершил(а) для кого-то?",
        "Какую песню ты бы посвятил(а) человеку, который тебе нравится?",
        "Что ты никогда не сделаешь на первом свидании?",
        "Если бы можно было вернуть бывшего(ую) на один день — кого и зачем?",
        "Что ты считаешь самым милым в отношениях?",
        "Каким должен быть идеальный партнёр в трёх словах?",
        "Чьё внимание ты хотел(а) получить, но не получил(а)?",
        "Ты более романтичный(ая) или более практичный(ая) в отношениях?",
    ],
    "hard": [
        "Кого из этого чата ты бы поцеловал(а), если бы пришлось выбрать?",
        "Самое странное место, где ты целовался(ась)?",
        "Что тебя заводит в человеке сильнее всего: ум, юмор или внешность?",
        "Что самое безумное ты вытворял(а) в подпитии?",
        "Кому из чата ты написал(а) бы «скучаю», если бы это не имело последствий?",
        "Какое самое откровенное признание ты слышал(а)?",
        "Ты когда-нибудь целовался(ась) с другом или подругой?",
        "Что ты думаешь об отношениях на одну ночь? Честно.",
        "С кем из присутствующих у тебя больше всего химии?",
        "Какой самый большой грех в твоей жизни, о котором никто не знает?",
        "Кого из присутствующих ты считаешь самым(ой) привлекательным(ой)?",
        "Ты когда-нибудь изменял(а) или был(а) близок(а) к этому?",
        "Опиши свой идеальный тип внешности и характера. Кто в чате ближе всего?",
        "Какая самая пикантная переписка у тебя была? Без подробностей.",
        "Сколько человек из чата, по-твоему, тайно в тебя влюблены?",
        "Ты встречался(ась) с двумя людьми одновременно?",
        "Что самое смелое ты хочешь сделать с человеком, который нравится?",
        "Какое самое неловкое утро после вечеринки было у тебя?",
        "Назови человека из чата, с которым ты бы не отказался(лась) оказаться запертым(ой) в лифте.",
        "Что тебя больше всего смущает в близости?",
        "Какая у тебя самая безумная идея для свидания?",
        "Какое твоё самое горячее воспоминание, о котором можно рассказать на публику?",
        "С кем из чата ты бы поспорил(а) на поцелуй и почему?",
        "Какой подкат из твоего арсенала ты считаешь безотказным?",
        "Что ты хотел(а) бы попробовать, но боишься признаться?",
        "Какую «взрослую» тайну знают о тебе всего один-два человека?",
        "У тебя было свидание, на котором ты сбежал(а)? Расскажи.",
        "Ты когда-нибудь влюблялся(ась) в чужого партнёра? Что сделал(а)?",
        "Кого из чата ты бы взял(а) с собой на романтическую поездку?",
        "Что самое дерзкое ты писал(а) человеку, который нравится?",
    ],
}

DARES = {
    "fun": [
        "Отправь в чат последнее фото из галереи (если не стыдно) или расскажи, что на нём.",
        "Изобрази любого человека из чата — остальные угадывают кого.",
        "Придумай прозвище каждому игроку и объясни его.",
        "Расскажи историю из своей жизни, в которой нужно соврать в одном месте. Остальные ищут ложь.",
        "Отправь в чат голосовое с песней, которую выберут остальные.",
        "Говори следующие 3 минуты только вопросами. Кто заметит ошибку — получит очко.",
        "Поменяй аватарку на любую смешную по выбору чата на один час.",
        "Сделай комплимент каждому игроку по очереди.",
        "Отправь в чат голосовое с любым животным звуком — остальные угадывают животное.",
        "Напиши в чат стих из 4 строк про любого игрока.",
        "Сделай селфи с самым смешным лицом и отправь в чат.",
        "Расскажи анекдот. Если никто не засмеётся — ты получаешь ещё штраф.",
        "Опиши свой день как футбольный комментатор.",
        "Изобрази голосом диктора новостей, что случилось в чате за последние 10 минут.",
        "Назови 10 стран за 20 секунд. Не успеешь — штраф.",
        "Покажи своё лучшее «вау»-выражение лица на фото и отправь в чат.",
        "Прочитай вслух последнее сообщение из любого чата (кроме личных тайн).",
        "Напиши в чат «Я лучший» и дождись, пока кто-нибудь поставит реакцию.",
        "Расскажи самую неловкую историю с тобой за последний месяц.",
        "Набери на телефоне любое слово носом и отправь результат в чат.",
        "Придумай рекламу самого ненужного предмета в твоей комнате.",
        "Расскажи о себе три факта: два правдивых и один ложный. Остальные угадывают ложный.",
        "Станцуй (или опиши свой танец) под песню, которую выберет группа.",
        "Напиши в чат смешное признание в любви к любому предмету вокруг тебя.",
        "Дай каждому игроку шуточную роль в фильме и объясни почему.",
        "Отправь в чат голосовое: прочитай скороговорку три раза подряд.",
        "Изобрази самое запоминающееся животное, пока группа не угадает.",
        "Опиши любого игрока тремя словами — группа угадывает кого.",
        "Назови 5 вещей, которые есть в твоей сумке или на столе, без подсматривания.",
        "Позвони (или напиши) другу и скажи только «Я всё знаю». Расскажи реакцию.",
    ],
    "love": [
        "Придумай подкат для любого игрока из чата и произнеси его вслух.",
        "Сделай комплимент каждому игроку, но только про его характер.",
        "Расскажи самую милую историю знакомства, которую слышал(а).",
        "Выбери игрока и придумай ему романтичное прозвище.",
        "Объясни в трёх предложениях, почему любой игрок из чата — идеальный партнёр.",
        "Отправь голосовое с признанием в любви кому-то из чата (в шутку).",
        "Напиши короткое романтическое сообщение выбранному игроку.",
        "Изобрази, как бы ты признавался(ась) в любви — остальные ставят оценку.",
        "Придумай название романтической комедии про двух игроков из чата.",
        "Расскажи, как ты флиртуешь: покажи один приём в чате.",
        "Выбери игрока и расскажи, какой подарок ему бы подарил(а).",
        "Опиши идеальное свидание для пары из двух игроков (выбери сам(а)).",
    ],
    "hard": [
        "Отправь последнему человеку, которому писал(а) комплимент, стикер ❤️ (если решишься).",
        "Расскажи самый пикантный секрет, который можно озвучить на публику.",
        "Остальные голосуют, кто самый(ая) опасный(ая) соблазнитель(ница). Назови причины.",
        "Сделай глоток любого напитка и расскажи самую смешную историю про свидание.",
        "Выбери игрока и пошли ему самый смелый комплимент (без пошлости).",
        "Напиши голосовое «Я скучаю» выбранному игроку (в шутку).",
        "Позови любого человека из контактов на кофе или чай. Покажи чату реакцию.",
        "Расскажи, что бы ты сделал(а) с любым игроком, если бы остались вдвоём на острове.",
        "Опиши самый смелый поступок на свидании, который ты готов(а) совершить.",
        "Покажи любому игроку (в личке) последнее фото в галерее и объясни, почему оно там.",
        "Выбери игрока и расскажи, что тебе в нём нравится больше всего.",
        "Отправь в чат голосовое с самым соблазнительным голосом, на который ты способен(на).",
        "Выбери игрока и скажи ему тост, как будто вы на свадьбе.",
        "Расскажи самое безумное, что ты сделал(а) ради человека, который нравился.",
        "Прочитай вслух самое смелое сообщение из своей переписки (имена скрыть).",
        "Дай телефон любому игроку: он выбирает любую вашу фотографию, а ты рассказываешь историю.",
    ],
}

# Штраф за отказ (задание сложнее или глоток)
PENALTIES = [
    "Сделай глоток любого напитка (вода и сок тоже подойдут) и расскажи самую неловкую историю в своей жизни.",
    "Отправь в чат голосовое с песней (минимум 15 секунд).",
    "Поменяй аватарку на любую, которую выберет группа, на 15 минут.",
    "Следующие 5 минут отвечай только в рифму. Ошибся — глоток.",
    "Сделай глоток и расскажи, что ты скрываешь от друзей.",
    "Назови всех игроков по очереди и скажи про каждого, что в нём бесит больше всего.",
    "Оставь в чате смешной ник на 10 минут (выберет группа).",
    "Выполни два задания подряд. Группа выбирает какие.",
    "Отправь в чат своё самое нелепое фото и объясни, откуда оно.",
    "Сделай глоток и сделай комплимент каждому игроку.",
    "Пропусти следующий свой ход (если игра идёт) и ответь на вопрос от группы.",
    "Расскажи тайну, о которой знают меньше трёх человек.",
    "Позвони любому из контактов и скажи: «Я только что проиграл(а) в игру, говори что-нибудь смешное».",
    "Изобрази танец живота (или другой танец) так, чтобы группа поставила оценку не ниже 7.",
    "Сделай глоток и ответь на вопрос, на который группа не получила ответа раньше.",
]
PENALTIES_HARD = [
    "Сделай два глотка и выбери игрока, которому придётся ответить на жёсткий вопрос.",
    "Отправь голосовое с признанием в любви случайному игроку (выберет группа).",
    "Расскажи самый откровенный секрет на публику и сделай глоток.",
    "Выбери любого игрока и поцелуй его в щёку (если согласится) или сделай три глотка.",
    "Сделай глоток и расскажи, кого из чата ты считаешь самым(ой) привлекательным(ой).",
    "Покажи в чате (голосовым или текстом) своё самое смелое «ночное» сообщение (имена скрыть).",
    "Выпей и отвечай «да» на все вопросы группы следующие 2 минуты.",
]

# «мешки»: вопросы выпадают без повторов, пока не закончится весь список
_bags: dict[tuple, list] = {}


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


def _stat(chat_id: int, uid: int, name: str) -> dict:
    cfg = settings.setdefault(str(chat_id), {})
    entry = cfg.setdefault("stats", {}).setdefault(str(uid), {"name": name, "lost": 0, "caught": 0})
    entry["name"] = name
    entry.setdefault("lost", 0)
    entry.setdefault("caught", 0)
    return entry


def add_loss(chat_id: int, uid: int, name: str) -> None:
    _stat(chat_id, uid, name)["lost"] += 1
    save_settings()


def add_caught(chat_id: int, uid: int, name: str) -> None:
    _stat(chat_id, uid, name)["caught"] += 1
    save_settings()


def allowed_cats(chat_id: int) -> list:
    return ["fun", "love"] + (["hard"] if adult_enabled(chat_id) else [])


def draw(chat_id: int, kind: str, category: str) -> str:
    """kind: 'q' — вопрос, 'd' — задание."""
    adult = adult_enabled(chat_id)
    if category == "hard" and not adult:
        category = "love"
    cats = allowed_cats(chat_id) if category == "all" else [category]
    key = (chat_id, kind, category, adult)
    if not _bags.get(key):
        src = QUESTIONS if kind == "q" else DARES
        bag = [t for c in cats for t in src[c]]
        random.shuffle(bag)
        _bags[key] = bag
    return _bags[key].pop()


def draw_penalty(chat_id: int) -> str:
    adult = adult_enabled(chat_id)
    key = (chat_id, "p", adult)
    if not _bags.get(key):
        bag = PENALTIES + (PENALTIES_HARD if adult else [])
        random.shuffle(bag)
        _bags[key] = bag
    return _bags[key].pop()


def cycle(seq: list, cur):
    try:
        return seq[(seq.index(cur) + 1) % len(seq)]
    except ValueError:
        return seq[0]


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
    phase: str = "lobby"          # lobby | turn | pick | busy
    last: int = 0
    turn: int = 0
    direction: int = 1
    target: int = TARGETS[0]
    max_step: int = STEPS[0]
    category: str = "all"
    fast: bool = False
    used_cards: set = field(default_factory=set)
    pick_by: tuple | None = None
    turn_token: int = 0
    move_id: int = 0              # номер хода: зашит в кнопки, чтобы отличать старые нажатия
    timer: asyncio.Task | None = None

    @property
    def turn_seconds(self) -> int:
        return FAST_SECONDS if self.fast else TURN_SECONDS


games: dict[int, Game] = {}


def mention(uid: int, name: str) -> str:
    return f'<a href="tg://user?id={uid}">{html.escape(name)}</a>'


def players_list(g: Game) -> str:
    return "\n".join(f"{i}. {mention(uid, n)}" for i, (uid, n) in enumerate(g.players, 1))


def lobby_text(g: Game) -> str:
    return (
        f"🎲 <b>Игра «{g.target}»</b>\n\n"
        f"Называем числа по кругу. За ход можно назвать следующее число "
        f"или поднять максимум на {g.max_step}. Кто назвал <b>{g.target}</b> — "
        f"выбирает вопрос или задание!\n\n"
        f"🎯 Цель: <b>{g.target}</b> · 📈 Шаг: до <b>+{g.max_step}</b>\n"
        f"🗂 Категория: <b>{CAT_LABEL[g.category]}</b>\n"
        f"⚡ Быстрый режим: <b>{'вкл (' + str(FAST_SECONDS) + ' сек)' if g.fast else 'выкл (' + str(TURN_SECONDS) + ' сек)'}</b>\n"
        f"🔞 Режим 18+: {'включён' if adult_enabled(g.chat_id) else 'выключен'}\n\n"
        f"🍀 На <b>{LUCKY}</b> — выбираешь, кому задать вопрос\n"
        f"😈 На <b>{REVERSE}</b> — порядок ходов разворачивается\n"
        f"🛡 У каждого одна карта: пропустить ход\n\n"
        f"<b>Игроки ({len(g.players)}):</b>\n{players_list(g)}\n\n"
        f"Настройки меняет создатель игры, а начать и отменить игру может любой."
    )


def lobby_kb(g: Game):
    kb = InlineKeyboardBuilder()
    kb.button(text="✋ Вступить", callback_data="join")
    kb.button(text="🚪 Выйти", callback_data="leave")
    kb.button(text=f"🎯 Цель: {g.target}", callback_data="set:target")
    kb.button(text=f"📈 Шаг: до +{g.max_step}", callback_data="set:step")
    kb.button(text=f"🗂 {CAT_LABEL[g.category]}", callback_data="set:cat")
    kb.button(text=f"⚡ Быстрый: {'вкл' if g.fast else 'выкл'}", callback_data="set:fast")
    kb.button(text="▶️ Начать", callback_data="begin")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


def turn_text(g: Game) -> str:
    uid, name = g.players[g.turn]
    lo = g.last + 1
    hi = min(g.last + g.max_step, g.target)
    card = "🛡 есть" if uid not in g.used_cards else "🛡 использована"
    arrow = "➡️" if g.direction == 1 else "⬅️"
    return (
        f"🔢 Последнее число: <b>{g.last}</b> (цель {g.target})\n"
        f"Ходит {arrow} {mention(uid, name)}\n"
        f"Можно назвать от <b>{lo}</b> до <b>{hi}</b> · ⏱ {g.turn_seconds} сек · карта: {card}"
    )


def turn_kb(g: Game):
    uid, _ = g.players[g.turn]
    kb = InlineKeyboardBuilder()
    nums = list(range(g.last + 1, min(g.last + g.max_step, g.target) + 1))
    for n in nums:
        kb.button(text=str(n), callback_data=f"num:{g.move_id}:{n}")
    rows = [len(nums)]
    if uid not in g.used_cards:
        kb.button(text="🛡 Пропустить ход", callback_data=f"skip:{g.move_id}")
        rows.append(1)
    kb.button(text="🛑 Остановить игру", callback_data="stopgame")
    rows.append(1)
    kb.adjust(*rows)
    return kb.as_markup()


def advance(g: Game) -> None:
    g.turn = (g.turn + g.direction) % len(g.players)


async def ack(c, text=None, show_alert=False) -> None:
    """Ответ на нажатие кнопки. Если Telegram вернул ошибку (например, query is too old) —
    игнорируем, чтобы игра не зависла."""
    try:
        await c.answer(text, show_alert=show_alert)
    except Exception as e:
        logging.warning("Не удалось ответить на нажатие кнопки: %s", e)


async def edit_msg(c, text: str, reply_markup=None) -> None:
    """Редактирование сообщения с кнопкой. Ошибки не должны ломать игру."""
    try:
        await c.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logging.warning("Не удалось изменить сообщение: %s", e)


async def safe_edit(bot: Bot, chat_id: int, message_id: int, text: str, kb=None) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb)
    except Exception:
        pass


async def remove_keyboard(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    except Exception:
        pass


# ---- таймеры игры -----------------------------------------------------------
def cancel_timer(g: Game) -> None:
    if g.timer and not g.timer.done():
        g.timer.cancel()
    g.timer = None


def start_timer(bot: Bot, g: Game, seconds: int, handler) -> None:
    cancel_timer(g)
    g.turn_token += 1
    g.timer = asyncio.create_task(_game_timer(bot, g, g.turn_token, seconds, handler))


async def _game_timer(bot: Bot, g: Game, token: int, seconds: int, handler) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    if games.get(g.chat_id) is not g or g.turn_token != token:
        return
    g.timer = None  # чтобы handler не отменил сам себя
    try:
        await handler(bot, g)
    except Exception:
        logging.exception("Ошибка в таймере игры")


async def send_turn(bot: Bot, g: Game) -> None:
    """Каждый ход — НОВОЕ сообщение, чтобы его было видно внизу чата."""
    g.phase = "turn"
    g.move_id += 1
    msg = await bot.send_message(g.chat_id, turn_text(g), reply_markup=turn_kb(g))
    g.message_id = msg.message_id
    start_timer(bot, g, g.turn_seconds, on_turn_timeout)


async def on_turn_timeout(bot: Bot, g: Game) -> None:
    if g.phase != "turn":
        return
    uid, name = g.players[g.turn]
    await remove_keyboard(bot, g.chat_id, g.message_id)
    await finish(bot, g, uid, name, f"⌛ {mention(uid, name)} не успел(а) сходить.")


async def on_pick_timeout(bot: Bot, g: Game) -> None:
    if g.phase != "pick":
        return
    picker = g.pick_by[0]
    others = [u for u, _ in g.players if u != picker]
    await do_pick(bot, g, random.choice(others), auto=True)


async def do_pick(bot: Bot, g: Game, target_uid: int, auto: bool = False) -> None:
    picker_uid, picker_name = g.pick_by
    tname = next(n for u, n in g.players if u == target_uid)
    g.phase = "busy"
    cancel_timer(g)
    q = draw(g.chat_id, "q", g.category)
    how = "бот выбрал(а) наугад" if auto else "выбрал(а)"
    await safe_edit(
        bot, g.chat_id, g.message_id,
        f"🍀 {mention(picker_uid, picker_name)} {how}: {mention(target_uid, tname)}!\n\n"
        f"❓ <b>{html.escape(q)}</b>\n\n"
        f"{html.escape(tname)}, отвечай вслух или в чате — игра идёт дальше ⏭",
    )
    g.pick_by = None
    advance(g)
    await send_turn(bot, g)


# ---- финал игры и раунд «вопрос/задание» -----------------------------------
@dataclass
class Round:
    id: str
    chat_id: int
    uid: int
    name: str
    voters: list
    category: str
    kind: str = ""        # q | d
    phase: str = "choose"  # choose | doing | vote | done
    message_id: int = 0
    votes: dict = field(default_factory=dict)
    timer: asyncio.Task | None = None


rounds: dict[str, Round] = {}
_round_ids = itertools.count(1)


def cancel_round_timer(r: Round) -> None:
    if r.timer and not r.timer.done():
        r.timer.cancel()
    r.timer = None


def set_round_timer(bot: Bot, r: Round, seconds: int, handler) -> None:
    cancel_round_timer(r)
    r.timer = asyncio.create_task(_round_timer(bot, r, seconds, handler))


async def _round_timer(bot: Bot, r: Round, seconds: int, handler) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return
    if rounds.get(r.id) is not r:
        return
    r.timer = None
    try:
        await handler(bot, r)
    except Exception:
        logging.exception("Ошибка в таймере раунда")


def choose_kb(r: Round):
    kb = InlineKeyboardBuilder()
    kb.button(text="❓ Вопрос", callback_data=f"r:{r.id}:q")
    kb.button(text="🔥 Задание", callback_data=f"r:{r.id}:d")
    kb.adjust(2)
    return kb.as_markup()


def doing_kb(r: Round):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ответил(а)" if r.kind == "q" else "✅ Выполнил(а)", callback_data=f"r:{r.id}:done")
    kb.button(text="🙅 Отказаться (штраф)", callback_data=f"r:{r.id}:skip")
    kb.adjust(1)
    return kb.as_markup()


def vote_kb(r: Round):
    kb = InlineKeyboardBuilder()
    if r.kind == "q":
        kb.button(text="👍 Верю", callback_data=f"r:{r.id}:yes")
        kb.button(text="👎 Врёт", callback_data=f"r:{r.id}:no")
    else:
        kb.button(text="👍 Засчитано", callback_data=f"r:{r.id}:yes")
        kb.button(text="👎 Не засчитано", callback_data=f"r:{r.id}:no")
    kb.adjust(2)
    return kb.as_markup()


def vote_text(r: Round) -> str:
    what = "ответил(а) честно" if r.kind == "q" else "выполнил(а) задание"
    return (
        f"🕵️ {mention(r.uid, r.name)} {what}?\n"
        f"Голосуют остальные игроки · ⏱ {VOTE_SECONDS} сек\n"
        f"Проголосовали: {len(r.votes)}/{len(r.voters)}"
    )


async def finish(bot: Bot, g: Game, uid: int, name: str, reason: str) -> None:
    cancel_timer(g)
    games.pop(g.chat_id, None)
    g.phase = "done"
    add_loss(g.chat_id, uid, name)
    r = Round(
        id=str(next(_round_ids)), chat_id=g.chat_id, uid=uid, name=name,
        voters=[u for u, _ in g.players if u != uid], category=g.category,
    )
    rounds[r.id] = r
    msg = await bot.send_message(
        g.chat_id,
        f"{reason}\n\n🎯 {mention(uid, name)}, выбирай: ❓ <b>вопрос</b> или 🔥 <b>задание</b>?\n"
        f"⏱ {CHOOSE_SECONDS} сек, иначе выберу сам",
        reply_markup=choose_kb(r),
    )
    r.message_id = msg.message_id
    set_round_timer(bot, r, CHOOSE_SECONDS, on_choose_timeout)


async def on_choose_timeout(bot: Bot, r: Round) -> None:
    if r.phase != "choose":
        return
    await begin_task(bot, r, random.choice(["q", "d"]), auto=True)


async def begin_task(bot: Bot, r: Round, kind: str, auto: bool = False) -> None:
    r.phase = "doing"
    r.kind = kind
    cancel_round_timer(r)
    text = draw(r.chat_id, kind, r.category)
    label = "вопрос" if kind == "q" else "задание"
    how = f"выбрал(а): <b>{label}</b>" if not auto else f"не выбрал(а), бот взял: <b>{label}</b>"
    await safe_edit(bot, r.chat_id, r.message_id, f"🎯 {mention(r.uid, r.name)} {how}")
    hint = "Ответь честно, потом нажми кнопку." if kind == "q" else "Выполни задание, потом нажми кнопку."
    msg = await bot.send_message(
        r.chat_id,
        f"{'❓' if kind == 'q' else '🔥'} {mention(r.uid, r.name)}, твой {label}:\n\n"
        f"<b>{html.escape(text)}</b>\n\n{hint}\nНе хочешь — отказывайся, но будет штраф. ⏱ {DOING_SECONDS} сек",
        reply_markup=doing_kb(r),
    )
    r.message_id = msg.message_id
    set_round_timer(bot, r, DOING_SECONDS, on_doing_timeout)


async def on_doing_timeout(bot: Bot, r: Round) -> None:
    if r.phase != "doing":
        return
    r.phase = "done"
    rounds.pop(r.id, None)
    await remove_keyboard(bot, r.chat_id, r.message_id)
    await bot.send_message(r.chat_id, f"⌛ {mention(r.uid, r.name)} так и не ответил(а). Идём дальше: /newgame")


async def start_vote(bot: Bot, r: Round) -> None:
    r.phase = "vote"
    cancel_round_timer(r)
    await remove_keyboard(bot, r.chat_id, r.message_id)
    msg = await bot.send_message(r.chat_id, vote_text(r), reply_markup=vote_kb(r))
    r.message_id = msg.message_id
    set_round_timer(bot, r, VOTE_SECONDS, on_vote_timeout)


async def on_vote_timeout(bot: Bot, r: Round) -> None:
    if r.phase == "vote":
        await resolve_vote(bot, r)


async def resolve_vote(bot: Bot, r: Round) -> None:
    r.phase = "done"
    cancel_round_timer(r)
    rounds.pop(r.id, None)
    await remove_keyboard(bot, r.chat_id, r.message_id)
    yes = sum(1 for v in r.votes.values() if v)
    no = len(r.votes) - yes
    who = mention(r.uid, r.name)
    if no > yes:
        add_caught(r.chat_id, r.uid, r.name)
        if r.kind == "q":
            extra = draw(r.chat_id, "q", r.category)
            text = (f"🤥 Большинство не поверило ({no}:{yes})! {who} получает ещё один вопрос:\n\n"
                    f"<b>{html.escape(extra)}</b>")
        else:
            extra = draw_penalty(r.chat_id)
            text = (f"🙅 Задание не засчитано ({no}:{yes})! {who}, штраф:\n\n"
                    f"<b>{html.escape(extra)}</b>")
        await bot.send_message(r.chat_id, text + "\n\nЕщё раз: /newgame")
    elif not r.votes:
        await bot.send_message(r.chat_id, f"🤷 Никто не проголосовал — засчитываем {who}. /newgame")
    else:
        await bot.send_message(r.chat_id, f"✅ Засчитано ({yes}:{no})! {who} молодец. Ещё раз: /newgame")


async def check_move(c, g, mid: int) -> bool:
    """Общая проверка нажатия на кнопки хода.
    Устаревшие и повторные нажатия обрабатываются тихо, без всплывающих окон «не твой ход»."""
    if not g or not g.started:
        await ack(c, "Эта игра уже закончилась.")
        return False
    if mid != g.move_id:
        await ack(c, "Этот ход уже сделан 👌")      # старое сообщение / повторное нажатие
        return False
    if g.phase != "turn":
        await ack(c)                                 # двойной клик: ход уже обрабатывается
        return False
    uid, name = g.players[g.turn]
    if c.from_user.id != uid:
        await ack(c, f"Сейчас ходит {name}")
        return False
    return True


async def stop_game(bot: Bot, chat_id: int) -> bool:
    """Останавливает игру и все незавершённые раунды в чате. Возвращает True, если что-то было."""
    stopped = False
    g = games.pop(chat_id, None)
    if g:
        cancel_timer(g)
        g.phase = "done"
        await remove_keyboard(bot, g.chat_id, g.message_id)
        stopped = True
    for r in [x for x in rounds.values() if x.chat_id == chat_id]:
        cancel_round_timer(r)
        r.phase = "done"
        rounds.pop(r.id, None)
        await remove_keyboard(bot, r.chat_id, r.message_id)
        stopped = True
    return stopped


async def open_lobby(bot: Bot, chat_id: int, uid: int, name: str) -> None:
    g = Game(chat_id=chat_id, host_id=uid)
    g.players.append((uid, name))
    games[chat_id] = g   # сразу, чтобы два /newgame подряд не создали две игры
    sent = await bot.send_message(chat_id, lobby_text(g), reply_markup=lobby_kb(g))
    g.message_id = sent.message_id


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    m = await bot.get_chat_member(chat_id, user_id)
    return m.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)


# ----------------------------------------------------------------------------
# Команды
# ----------------------------------------------------------------------------
RULES = (
    "🎲 <b>Игра «21»</b>\n\n"
    "Игроки по очереди называют числа. За ход можно назвать следующее число "
    "или поднять максимум на 3 (сказали 1 — можно 2, 3 или 4). "
    "Кто назвал последнее число (21) — выбирает ❓ вопрос или 🔥 задание. "
    "Остальные голосуют, честно ли он справился. Не врёт — молодец, "
    "врёт — получает ещё вопрос. Можно отказаться, но тогда штраф.\n\n"
    "🍀 Число 7 — выбираешь, кому задать вопрос.\n"
    "😈 Число 13 — порядок ходов разворачивается.\n"
    "🛡 У каждого одна карта: пропустить свой ход.\n"
    "⚙️ Создатель выбирает цель (15/21/31/51), шаг (2/3/5), категорию и быстрый режим.\n\n"
    "<b>Команды (в группе):</b>\n"
    "/newgame — новая игра\n"
    "/stop — остановить игру (может любой)\n"
    "/question — случайный вопрос\n"
    "/dare — случайное задание\n"
    "/rating — рейтинг чата\n"
    "/mode18 — вкл/выкл 18+ (только админы)\n"
    "/rules — правила"
)

GROUP_COMMANDS = [
    BotCommand(command="newgame", description="Новая игра"),
    BotCommand(command="stop", description="Остановить игру"),
    BotCommand(command="question", description="Случайный вопрос"),
    BotCommand(command="dare", description="Случайное задание"),
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
async def cmd_newgame(m: Message, bot: Bot):
    if not in_group(m):
        await m.answer("Игра работает только в группах. Добавь меня в группу и напиши /newgame 🙂")
        return
    if m.chat.id in games:
        kb = InlineKeyboardBuilder()
        kb.button(text="♻️ Остановить её и начать новую", callback_data="restart")
        await m.reply("В этом чате уже идёт игра. Остановить: /stop", reply_markup=kb.as_markup())
        return
    await open_lobby(bot, m.chat.id, m.from_user.id, m.from_user.full_name)


@router.message(Command("stop"))
async def cmd_stop(m: Message, bot: Bot):
    if not await stop_game(bot, m.chat.id):
        await m.reply("Сейчас нет активной игры.")
        return
    await m.answer(f"🛑 {mention(m.from_user.id, m.from_user.full_name)} остановил(а) игру. Новая игра: /newgame")


@router.message(Command("question"))
async def cmd_question(m: Message):
    await m.answer(f"❓ <b>{html.escape(draw(m.chat.id, 'q', 'all'))}</b>")


@router.message(Command("dare"))
async def cmd_dare(m: Message):
    await m.answer(f"🔥 <b>{html.escape(draw(m.chat.id, 'd', 'all'))}</b>")


@router.message(Command("rating"))
async def cmd_rating(m: Message):
    stats = settings.get(str(m.chat.id), {}).get("stats", {})
    losers = sorted((e for e in stats.values() if e.get("lost", 0) > 0), key=lambda e: e["lost"], reverse=True)[:10]
    if not losers:
        await m.answer("Рейтинг пока пуст. Сыграйте в /newgame!")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else str(i + 1) + '.'} {html.escape(e['name'])} — {e['lost']}"
        for i, e in enumerate(losers)
    ]
    text = "🏆 <b>Кто чаще всех называл последнее число:</b>\n\n" + "\n".join(lines)
    liars = sorted((e for e in stats.values() if e.get("caught", 0) > 0), key=lambda e: e["caught"], reverse=True)[:3]
    if liars:
        text += "\n\n🤥 <b>Чаще всех ловили на вранье:</b>\n" + "\n".join(
            f"{html.escape(e['name'])} — {e['caught']}" for e in liars
        )
    await m.answer(text)


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
        "🔞 Режим 18+ <b>включён</b>: доступна категория «Жёсткие 18+»." if cfg["adult"]
        else "✅ Режим 18+ <b>выключен</b>."
    )


# ----------------------------------------------------------------------------
# Кнопки лобби
# ----------------------------------------------------------------------------
@router.callback_query(F.data == "join")
async def cb_join(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await ack(c, "Набор в игру закрыт.", show_alert=True)
        return
    if any(uid == c.from_user.id for uid, _ in g.players):
        await ack(c, "Ты уже в игре!")
        return
    if len(g.players) >= MAX_PLAYERS:
        await ack(c, "Игра заполнена.", show_alert=True)
        return
    g.players.append((c.from_user.id, c.from_user.full_name))
    await edit_msg(c, lobby_text(g), reply_markup=lobby_kb(g))
    await ack(c, "Ты в игре!")


@router.callback_query(F.data == "leave")
async def cb_leave(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await ack(c, )
        return
    g.players = [(u, n) for u, n in g.players if u != c.from_user.id]
    if not g.players:
        games.pop(g.chat_id, None)
        await edit_msg(c, "Все вышли, игра отменена.")
        await ack(c, )
        return
    if g.host_id == c.from_user.id:
        g.host_id = g.players[0][0]
    await edit_msg(c, lobby_text(g), reply_markup=lobby_kb(g))
    await ack(c, "Ты вышел(а).")


@router.callback_query(F.data.startswith("set:"))
async def cb_set(c: CallbackQuery):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await ack(c, )
        return
    if c.from_user.id != g.host_id:
        await ack(c, "Настройки меняет создатель игры.")
        return
    what = c.data[4:]
    if what == "target":
        g.target = cycle(TARGETS, g.target)
    elif what == "step":
        g.max_step = cycle(STEPS, g.max_step)
    elif what == "cat":
        g.category = cycle(["all", "fun", "love"] + (["hard"] if adult_enabled(g.chat_id) else []), g.category)
    elif what == "fast":
        g.fast = not g.fast
    await edit_msg(c, lobby_text(g), reply_markup=lobby_kb(g))
    await ack(c, )


@router.callback_query(F.data == "cancel")
@router.callback_query(F.data == "stopgame")
async def cb_cancel(c: CallbackQuery, bot: Bot):
    """Отменить лобби или остановить идущую игру может любой человек в чате."""
    chat_id = c.message.chat.id
    who = mention(c.from_user.id, c.from_user.full_name)
    if not await stop_game(bot, chat_id):
        await ack(c, "Игра уже закончилась.")
        return
    await ack(c, "Игра остановлена.")
    if c.data == "cancel":
        await edit_msg(c, f"❌ {who} отменил(а) игру.")
    else:
        await bot.send_message(chat_id, f"🛑 {who} остановил(а) игру. Новая игра: /newgame")


@router.callback_query(F.data == "restart")
async def cb_restart(c: CallbackQuery, bot: Bot):
    """Остановить идущую игру и сразу открыть набор в новую — может любой человек."""
    chat_id = c.message.chat.id
    who = mention(c.from_user.id, c.from_user.full_name)
    await stop_game(bot, chat_id)
    await ack(c, "Начинаем заново!")
    await edit_msg(c, f"♻️ {who} остановил(а) прошлую игру.")
    await open_lobby(bot, chat_id, c.from_user.id, c.from_user.full_name)


@router.callback_query(F.data == "begin")
async def cb_begin(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    if not g or g.started:
        await ack(c, )
        return
    if len(g.players) < 2:
        await ack(c, "Нужно минимум 2 игрока!", show_alert=True)
        return
    random.shuffle(g.players)
    g.started = True
    g.last = 0
    g.turn = 0
    await edit_msg(c, 
        f"🎲 <b>Игра «{g.target}» началась!</b>\n"
        f"Шаг: до +{g.max_step} · {CAT_LABEL[g.category]} · "
        f"{'⚡ быстрый режим' if g.fast else 'обычный режим'}\n\n"
        f"<b>Порядок ходов:</b>\n{players_list(g)}",
        reply_markup=None,
    )
    await ack(c, "Поехали!")
    await send_turn(bot, g)


# ----------------------------------------------------------------------------
# Кнопки игры
# ----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("num:"))
async def cb_number(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    try:
        _, mid, num = c.data.split(":")
        mid, n = int(mid), int(num)
    except ValueError:
        await ack(c, "Эта кнопка устарела. Новая игра: /newgame")
        return
    if not await check_move(c, g, mid):
        return
    uid, name = g.players[g.turn]
    if not (g.last + 1 <= n <= min(g.last + g.max_step, g.target)):
        await ack(c, "Так нельзя.")
        return

    # сначала меняем состояние (без await), чтобы двойной клик не прошёл дважды
    g.last = n
    g.phase = "busy"
    cancel_timer(g)
    await ack(c, f"Ты назвал(а) {n}")

    if n >= g.target:
        await edit_msg(c, 
            f"✅ {mention(uid, name)} назвал(а) <b>{n}</b>", reply_markup=None
        )
        await finish(bot, g, uid, name, f"💥 {mention(uid, name)} дошёл(ла) до {g.target}!")
        return

    if n == LUCKY:
        g.pick_by = (uid, name)
        await edit_msg(c, 
            f"✅ {mention(uid, name)} назвал(а) <b>{n}</b> 🍀", reply_markup=None
        )
        kb = InlineKeyboardBuilder()
        for pu, pn in g.players:
            if pu != uid:
                kb.button(text=pn[:20], callback_data=f"pick:{pu}")
        kb.adjust(2)
        msg = await bot.send_message(
            g.chat_id,
            f"🍀 <b>Счастливая семёрка!</b>\n{mention(uid, name)}, выбери, кому задать вопрос "
            f"(⏱ {PICK_SECONDS} сек, иначе выберу наугад):",
            reply_markup=kb.as_markup(),
        )
        g.message_id = msg.message_id
        g.phase = "pick"
        start_timer(bot, g, PICK_SECONDS, on_pick_timeout)
        return

    if n == REVERSE:
        g.direction *= -1
        advance(g)
        await edit_msg(c, 
            f"✅ {mention(uid, name)} назвал(а) <b>{n}</b>\n😈 Чёртова дюжина! Порядок ходов развернулся 🔄",
            reply_markup=None,
        )
        await send_turn(bot, g)
        return

    advance(g)
    # старое сообщение остаётся в истории с результатом хода, без кнопок
    await edit_msg(c, f"✅ {mention(uid, name)} назвал(а) <b>{n}</b>", reply_markup=None)
    await send_turn(bot, g)


@router.callback_query(F.data.startswith("skip"))
async def cb_skip(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    try:
        mid = int(c.data.split(":")[1])
    except (IndexError, ValueError):
        await ack(c, "Эта кнопка устарела. Новая игра: /newgame")
        return
    if not await check_move(c, g, mid):
        return
    uid, name = g.players[g.turn]
    if uid in g.used_cards:
        await ack(c, "Карта уже использована.")
        return
    g.used_cards.add(uid)
    g.phase = "busy"
    cancel_timer(g)
    await ack(c, "Ход пропущен!")
    advance(g)
    await edit_msg(c, 
        f"🛡 {mention(uid, name)} использовал(а) карту и пропускает ход (число остаётся {g.last})",
        reply_markup=None,
    )
    await send_turn(bot, g)


@router.callback_query(F.data.startswith("pick:"))
async def cb_pick(c: CallbackQuery, bot: Bot):
    g = games.get(c.message.chat.id)
    if not g or g.phase != "pick" or not g.pick_by:
        await ack(c, "Выбор уже сделан 👌")
        return
    if c.from_user.id != g.pick_by[0]:
        await ack(c, "Выбирает только тот, кто назвал 7.")
        return
    if c.message.message_id != g.message_id:
        await ack(c, "Это старая кнопка.")
        return
    target = int(c.data.split(":")[1])
    if not any(u == target for u, _ in g.players) or target == g.pick_by[0]:
        await ack(c, "Так нельзя.")
        return
    g.phase = "busy"
    await ack(c, "Выбрано!")
    await do_pick(bot, g, target)


# ----------------------------------------------------------------------------
# Кнопки раунда «вопрос/задание» и голосования
# ----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("r:"))
async def cb_round(c: CallbackQuery, bot: Bot):
    try:
        _, rid, act = c.data.split(":")
    except ValueError:
        await ack(c, )
        return
    r = rounds.get(rid)
    if not r:
        await ack(c, "Раунд уже закончился.")
        return
    uid = c.from_user.id

    if act in ("q", "d"):
        if uid != r.uid:
            await ack(c, f"Выбирает только {r.name}.", show_alert=False)
            return
        if r.phase != "choose":
            await ack(c, )
            return
        r.phase = "busy"
        await ack(c, )
        await begin_task(bot, r, act)

    elif act == "done":
        if uid != r.uid:
            await ack(c, f"Нажимает только {r.name}.", show_alert=False)
            return
        if r.phase != "doing":
            await ack(c, )
            return
        r.phase = "busy"
        await ack(c, "Отлично! Теперь голосование.")
        await start_vote(bot, r)

    elif act == "skip":
        if uid != r.uid:
            await ack(c, f"Нажимает только {r.name}.", show_alert=False)
            return
        if r.phase != "doing":
            await ack(c, )
            return
        r.phase = "done"
        cancel_round_timer(r)
        rounds.pop(r.id, None)
        await ack(c, )
        await remove_keyboard(bot, r.chat_id, r.message_id)
        pen = draw_penalty(r.chat_id)
        await bot.send_message(
            r.chat_id,
            f"🙅 {mention(r.uid, r.name)} отказался(лась)! Штраф:\n\n<b>{html.escape(pen)}</b>\n\nЕщё раз: /newgame",
        )

    elif act in ("yes", "no"):
        if r.phase != "vote":
            await ack(c, "Голосование закончилось.")
            return
        if uid == r.uid:
            await ack(c, "За себя голосовать нельзя 🙂")
            return
        if uid not in r.voters:
            await ack(c, "Голосуют только игроки этой игры.")
            return
        r.votes[uid] = (act == "yes")
        await ack(c, "Голос принят!")
        if r.phase != "vote":   # пока отвечали, таймер уже подвёл итог
            return
        if len(r.votes) >= len(r.voters):
            await resolve_vote(bot, r)
        else:
            await safe_edit(bot, r.chat_id, r.message_id, vote_text(r), vote_kb(r))
    else:
        await ack(c, )


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
