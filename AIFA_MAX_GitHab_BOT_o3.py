# AIFA MAX BOT  •  17-05-2025 21:00  •  o3.1-patch
#
# ────────────────────────────────────────────────────────────────
# Функционал:
#   • Принимает файлы из Telegram.
#   • Генерирует имена через GPT-4o-mini.
#   • Сохраняет на диск, ведёт историю, логи, пересчитывает токены.
#   • GUI на Tkinter + иконка в system tray.
# ────────────────────────────────────────────────────────────────

# Апгрейд версии o1:
# 1. Убрал двойной jpg.
# 2. Сделал сворачивание в system tray.
# 3. Оценка 0 - теперь даёт вводить имя вручную.
# 4. Замьючен таймер.
# 5. Добавленна безопасность/список пользователей которым разрешён доступ.

# Апгрейд версии o2:
# 1. Востановленно сообщение о входе пользователя для создателя. 
# 2. Сделано уведомление о нажатии кнопки "поддержать проект".
# 3. API теперь загружаются из переменных сред windows.
# 4. API проверяются на наличие и работоспособность.
# 5. Аккуратно выстроенны и подписанны импорты.
# 6. Добавленно вычеление по последним операциям, имини и id пользователя который нажал поддержать проект.
# 7. Введён пробел между словами через переменную "sep"
# 8. Исключение для повторения названий одного файла

# Апгрейд версия o3:
# 1. Переструктурированы импорты; добавлены base64, colorchooser, ttk
# 2. Конфиг: openai_model, ui_color, ui_color_light, naming_prompt; загрузка allowed_users
# 3. Динамическая ACL: загрузка из конфига; GUI-диалог одобрения/отказа
# 4. GUI «Настройки»: редактирование промта, выбор модели, управление пользователями, выбор цвета
# 5. Перерисовка градиента: хранение ID прямоугольников, обновление при смене цвета
# 6. gpt_name: унификация формата сообщений; поддержка списка попыток; lowercase и обрезка
# 7. Анализ фото: диалог загрузки, пользовательский промт, отправка base64 в GPT-4o, вывод описания
# 8. Телеграм-бот (PTB v21+): обновлены хэндлеры переименования и рейтингов для режимов AI/OneName и ручного ввода

# Модули:
# - load_cfg/save_cfg: I/O config.json с дефолтами и валидацией
# - load_name_history/save_name_history: хранение name_history.json
# - verify_token: асинхронная проверка токена Telegram через Bot.get_me()
# - gpt_name: формирование запросов OpenAI; учёт типа файла и правил именования
# - mix_color: интерполяция HEX-цветов и вычисление светлой версии
# - FancyGUI: Tkinter UI с градиентом, меню настроек и анализа фото, статус и контролы
# - _bot_thread: хэндлеры Telegram (/start, приём файлов, рейтинги, колбэки)
# - _open_photo_menu: workflow анализа изображения
# - UI-настройки: селектор модели, Treeview белого списка, редактор промта


# -  !Вернуть определение последнего пользователя, для кнопки поддежрка
#    !1. Включить возможность отправки разработчику фото, видео и любых файлов.
#    !2. Проверить счётчик токенов и средств.
#    !3. Сделать дистанционное управление с телефона.
#    !4. Подумать о встроенном VPN, туннеле или другом способе обхода блокировки OpenAI.
#    !5. Вести статистику потраченных токенов по моделям за время пользования.
#    !6. Сделать промтовед.
#    !7. Сделать прайс по версиям GPT	
#    !8. Написать мини апку	
#    !9. Написать версии на другие OS
#    !10. Сделать тайный кабинет разработчика
#    !11. Сделать что пр инажатии на иконку вылетал поверх всех окон
#    !12. Сделать окно для воода промта/(анализ фото) больше
#    !13. Сделать чтоб предлогал название для видео
#    !14. Сделать чтоб мог отправлять большие фотографии 
#    !15. Когда кидаешь много разных файлов пакетом, переименовывает разрешение.


import os, asyncio, json, logging, threading, re, requests
import base64
from pathlib import Path
from uuid import uuid4
from decimal import Decimal, getcontext

# Tkinter + PIL + pystray
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import colorchooser 
from tkinter import ttk   
import pystray
from PIL import Image, ImageDraw

# Telegram / PTB v21+
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import InvalidToken
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# OpenAI async-клиент
from openai import AsyncOpenAI

# ────────────────────────────────────────────────────────────────
BASE_DIR           = Path(__file__).parent
LOG_PATH           = BASE_DIR / "bot.log"
CONFIG_PATH        = BASE_DIR / "config.json"
RATING_PATH        = BASE_DIR / "ratings.json"
HISTORY_PATH       = BASE_DIR / "name_history.json"
OPENAI_MODEL       = "gpt-4o-mini"
PURPLE_DARK        = "#6a0dad"
PURPLE_LIGHT       = "#b57bff"
MASK_COLOR         = "#00ff00"
ALLOWED_IDS: set[int] = set()  # сюда пользователь сам добавит ID, если захочет

# --- ключи из переменных среды ---
PROFILE = os.getenv("AIFA_MAX_PROFILE", "DEFAULT")  # Профиль. По умолчанию DEFAULT. Можно переопределить через AIFA_MAX_PROFILE.
TOKEN       = os.getenv(f"AIFA_MAX_{PROFILE}_TELEGRAM")
OPENAI_KEY  = os.getenv(f"AIFA_MAX_{PROFILE}_OPENAI")
try:
    CREATOR_CHAT_ID = int(os.environ["CREATOR_CHAT_ID"])
except (KeyError, ValueError):
    raise RuntimeError("Переменная окружения CREATOR_CHAT_ID должна быть числом")

if not TOKEN:
    raise RuntimeError(f"Переменная окружения AIFA_MAX_{PROFILE}_TELEGRAM не найдена")
if not OPENAI_KEY:
    raise RuntimeError(f"Переменная окружения AIFA_MAX_{PROFILE}_OPENAI не найдена")

# --- логирование ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, "a", "utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# --- конфиг по умолчанию ---
DEFAULT_CFG = {
    "doc_dir":   str(BASE_DIR),
    "photo_dir": str(BASE_DIR),
    "video_dir": str(BASE_DIR),
    "token_price_usd": 0.15,
    "openai_model": "gpt-4o-mini",
    "ui_color": PURPLE_DARK,               #  ← ДОБАВИТЬ
    "ui_color_light": PURPLE_LIGHT,
    "allowed_ids":    [],     
    "naming_prompt":  ""
}

def load_cfg() -> dict:
    """Чтение config.json с дефолтами и валидацией."""
    try:
        data = json.loads(CONFIG_PATH.read_text("utf-8"))
        cfg = {**DEFAULT_CFG, **data}
    except Exception as e:
        log.warning(f"Не удалось загрузить config.json: {e}")
        cfg = DEFAULT_CFG.copy()
    if cfg.get("token_price_usd", 0) < 0.001:
        cfg["token_price_usd"] = DEFAULT_CFG["token_price_usd"]
        save_cfg(cfg)
    return cfg

def save_cfg(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    
def get_allowed_ids(cfg: dict) -> set[int]:
    """Преобразует cfg["allowed_ids"] → множество int (без пустых)."""
    try:
        return {int(i) for i in cfg.get("allowed_ids", []) if str(i).strip()}
    except ValueError:
        return set()    

def load_name_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text("utf-8"))
        except Exception as e:
            log.warning(f"Не удалось загрузить историю имён: {e}")
    return {}

def save_name_history(history: dict) -> None:
    try:
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:
        log.error(f"Ошибка сохранения истории имён: {e}")

# асинхронная валидация токена Telegram
async def verify_token(bot: Bot):
    try:
        await bot.get_me()
    except InvalidToken:
        raise RuntimeError("Указан некорректный Telegram-токен")
# ────────────────────────────────────────────────────────────────
#  Градиент и генерация имён через GPT
# ────────────────────────────────────────────────────────────────
client = AsyncOpenAI(api_key=OPENAI_KEY)

def mix_color(c1: str, c2: str, t: float) -> str:
    """Возвращает HEX-цвет между c1 и c2 (t∈[0,1])."""
    h = lambda s, i: int(s[i:i+2], 16)
    r = int(h(c1,1) + (h(c2,1)-h(c1,1))*t)
    g = int(h(c1,3) + (h(c2,3)-h(c1,3))*t)
    b = int(h(c1,5) + (h(c2,5)-h(c1,5))*t)
    return f"#{r:02x}{g:02x}{b:02x}"

async def gpt_name(
    prompt: str,
    image_url: str | None = None,
    variant: int = 1,
    prev_names: list[str] | None = None
) -> tuple[str | None, int]:
    """
    Запрашивает у GPT короткое имя (1-3 слова, строчными, без расширения).
    Возвращает (имя|None, кол-во токенов).
    """
    SEP = " "
    prev_names = prev_names or []

    # разрешаем ли личные имена?
    allow_person = bool(re.search(r"(?:имя|зовут|называется|это)\s+[А-Яа-яЁё]+", prompt, re.I))

    # --- анализ прошлых попыток, чтобы GPT «учился» ---
    feedback_lines: list[str] = []
    for entry in (prev_names or []):
        # поддерживаем два формата: dict{name,rating,comment} или просто строку
        if isinstance(entry, dict):
            name = entry.get("name")
            rating = entry.get("rating")
            comment = entry.get("comment", "")
        else:
            name, rating, comment = entry, None, ""
        if name and rating is not None:
            line = f"- «{name}» → оценка {rating}"
            if comment:
                line += f": «{comment}»"
            feedback_lines.append(line)
    feedback_text = ""
    if feedback_lines:
        feedback_text = (
            "Ты уже предлагал:\n"
            + "\n".join(feedback_lines)
            + "\nУчитывай эти оценки, чтобы улучшаться."
        )

    sys_msg = (
        "Ты — генератор коротких русских названий файлов "
        "(1–3 слова, строчные буквы, между словами пробел, без расширения). "
        "Не повторяй уже предложенные варианты."
    )
    if not allow_person:
        sys_msg += " Без собственных имён людей."

    if variant == 2:
        sys_msg = sys_msg.replace("коротких", "других коротких", 1)

    messages = [{"role": "system", "content": sys_msg}]
    if image_url:

        # вставляем feedback_text после prompt (если он есть)
        user_txt = prompt[:200] + (f"\n{feedback_text}" if feedback_text else "")
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": user_txt},
            ]
        })

    else:
        user_content = prompt[:4000] + (f"\n{feedback_text}" if feedback_text else "")
        messages.append({"role": "user", "content": user_content})

    try:
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, max_tokens=12
        )
        raw = resp.choices[0].message.content.strip()
        candidate = re.sub(r"\s+", SEP, raw).lower()
        candidate = re.sub(r"\.(?:jpe?g|png|mp4|mov|docx?)$", "", candidate, flags=re.I)[:50]
        return candidate or None, resp.usage.total_tokens
    except Exception as e:
        log.warning(f"GPT-ошибка: {e}")
        return None, 0
# ────────────────────────────────────────────────────────────────
class FancyGUI(tk.Tk):
    """Tk-GUI + логика Telegram-бота."""
    WIDTH, HEIGHT = 520, 380
    MAX_PI_WIDTH  = 68          # ширина бегущей строки π

    # ---------- конструктор ----------
    def __init__(self):
        super().__init__()

        # ╭─── общие свойства окна ────────────────────────────────────╮
        self.overrideredirect(True)                # без обрамления
        self.configure(bg=MASK_COLOR)
        self.wm_attributes("-transparentcolor", MASK_COLOR)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+200+150")
        # ╰────────────────────────────────────────────────────────────╯

        # ─── 1. Конфиг и цветовая схема ──────────────────────────────
        self.cfg = load_cfg()

        # список допущенных ID из конфига + «всегда разрешённые» DEFAULT_ALLOWED
        self.allowed_users: set[int] = {
            u["id"] for u in self.cfg.get("allowed_users", [])
        } | ALLOWED_IDS | {CREATOR_CHAT_ID}

        # цвета интерфейса
        self.ui_color        = self.cfg.get("ui_color",        PURPLE_DARK)
        self.ui_color_light  = self.cfg.get("ui_color_light",  PURPLE_LIGHT)

        # ─── 1-b. Текущая модель OpenAI ──────────────────────────────
        global OPENAI_MODEL           # будем менять «глобал» при выборе
        OPENAI_MODEL = self.cfg.get("openai_model", "gpt-4o-mini")
        self.openai_model_var = tk.StringVar(value=OPENAI_MODEL)

        # ─── 2. Прочие служебные поля ────────────────────────────────
        self.name_history      = load_name_history()
        self.last_file_id      = None
        self.base_stem         = ""
        self.rating_sum        = 0
        self.rating_count      = 0
        self.tokens            = 0
        self.total_rubles      = 0.0
        self.ai                = True
        self.conn              = False
        self.openai_ok         = True
        self.one_name_mode     = False
        self.current_series_name = ""
        self.series_counter    = 1
        self.last_out_path     = None
        self.rating_timer      = None
        self.series_timer      = None
        self.waiting_manual_name: dict[int,str] = {}  # chat_id→file_id
        self.pending_series_files: list[Path] = []
        self.last_user         = None            # telegram.User
        self.app, self.loop    = None, None      # появятся позже
        
        # ─── 3. Drag-&-drop окна ─────────────────────────────────────
        self.bind("<ButtonPress-1>",
                  lambda e: (setattr(self, "_x", e.x), setattr(self, "_y", e.y)))
        self.bind("<B1-Motion>",
                  lambda e: self.geometry(f"+{self.winfo_pointerx()-self._x}"
                                          f"+{self.winfo_pointery()-self._y}"))

        # ─── 4. Canvas с градиентом ───────────────────────────────────
        cv = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                       bg=MASK_COLOR, highlightthickness=0)
        cv.pack(fill="both", expand=True)                                          

               # сохраняем id прямоугольников, чтобы потом можно было перекрасить
        self.gradient_rects: list[int] = []
        for i in range(40):
            y0 = int(self.HEIGHT *  i    / 39)
            y1 = int(self.HEIGHT * (i+1) / 39)
            rect_id = cv.create_rectangle(
                0, y0, self.WIDTH, y1,
                fill=mix_color(self.ui_color, self.ui_color_light, i/39),
                outline=""
            )
            self.gradient_rects.append(rect_id)

        cv.create_oval(5, 5, self.WIDTH-5, self.HEIGHT-5, outline="", fill="")
        cv.create_text(self.WIDTH//2, 15, text="AIFA",
                       fill="white", font=("Segoe UI", 23, "bold"))
        cv.create_text(self.WIDTH//2, 40, text="AI File Assistant Max",
                       fill="white", font=("Segoe UI", 14, "italic"))
        cv.create_text(self.WIDTH//2, 60, text="t.me/AIFA_MAX_XXX_BOT",
                       fill="white", font=("Segoe UI", 10, "italic"))
        self.canvas = cv

        # --- элементы управления ---
        self._build_paths()
        self._build_status()
        self._build_ai_switch()
        self._build_one_name_switch()
        self._build_currency_display()

        # --- верхние кнопки [—] [×] ---
        BTN, GAP, OFFR, OFFT = 22, 5, 10, 8
        btn_close = tk.Button(cv, text="✕", font=("Segoe UI", 10, "bold"), fg="white",
                              bg="#ff4d4d", activebackground="#ff6666", relief="flat", command=self.destroy)
        btn_hide  = tk.Button(cv, text="—", font=("Segoe UI", 10, "bold"), relief="flat", command=self._on_close)
        btn_close.place(relx=1.0, anchor="ne", x=-(OFFR+BTN),           y=OFFT, width=BTN, height=BTN)
        btn_hide .place(relx=1.0, anchor="ne", x=-(OFFR+BTN+GAP+BTN),   y=OFFT, width=BTN, height=BTN)
        for b in (btn_close, btn_hide):
            b.configure(highlightthickness=0, bd=0)

        # --- нижние кнопки ---
        tk.Button(cv, text="⚙ Настройки", font=("Segoe UI",10,"bold"), command=self._open_settings_menu)\
            .place(x=40,  y=320, width=140, height=28)
        tk.Button(cv, text="О боте",       font=("Segoe UI",10,"bold"), command=self._open_about_menu)\
            .place(x=190, y=320, width=140, height=28)
        tk.Button(cv, text="🖼 Анализ фото", font=("Segoe UI",10,"bold"), command=self._open_photo_menu)\
            .place(x=340, y=320, width=140, height=28)

        # --- бегущая строка π ---
        self.PI = self._generate_pi(50)
        self._pi_idx = 0
        self.lbl_pi = tk.Label(cv, text="π = ", fg="black", font=("Courier New", 10))
        self.lbl_pi.place(x=40, y=self.HEIGHT-25)
        self._update_pi()

        # --- иконка в трее и бот ---
        self._create_tray_icon()
        self.after(0, self._check_openai)
        threading.Thread(target=self._bot_thread, daemon=True).start()
        
    # ────────────────────────────────────────────────────────────────
    #  Сохранение / обновление списка доступа
    # ────────────────────────────────────────────────────────────────
    def _save_allowed_users(self, lst: list[dict]) -> None:
        """
        Перезаписывает список допущенных пользователей в config.json,
        а также обновляет in-memory множество self.allowed_users.
        """
        self.cfg["allowed_users"] = lst
        save_cfg(self.cfg)

        # пересчёт множества ID
        self.allowed_users = {u["id"] for u in lst}

        # показать информацию в строке статуса
        self._status(f"Всего разрешённых: {len(self.allowed_users)}")        
    # ────────────────────────────────────────────────────────────────
    #  ВСТАВЬТЕ где-нибудь внутри класса FancyGUI (например сразу
    #  после _status / _fname – места не принципиально)
    # ────────────────────────────────────────────────────────────────
    def _request_access_dialog(self, user, upd, ctx):
        """
        Вызвается из _cmd_start через self.after().
        Показывает диалог с кнопками «Разрешить / Отказать».
        """
        win = tk.Toplevel(self)
        win.title("Запрос на доступ")
        win.geometry("320x180")
        win.transient(self); win.grab_set()

        full = f"{user.first_name or ''} {user.last_name or ''}".strip()
        login = f"@{user.username}" if user.username else "(нет логина)"

        tk.Label(
            win, text="Новый пользователь хочет доступ:", font=("Segoe UI", 10, "bold")
        ).pack(pady=(15, 6))
        tk.Label(win, text=f"ID: {user.id}\n{full}\n{login}", justify="center")\
            .pack(pady=4)

        # ------- колбэки двух кнопок -------
        def allow():
            # 1. дописываем в конфиг
            lst = self.cfg.get("allowed_users", [])
            lst.append({"id": user.id, "name": full, "login": login})
            self._save_allowed_users(lst)               # ← ваш helper
            # 2. отвечаем пользователю
            asyncio.run_coroutine_threadsafe(
                ctx.bot.send_message(user.id, "✅ Доступ разрешён!"),
                self.loop
            )
            # 3. закрываем окно
            win.destroy()

        def deny():
            asyncio.run_coroutine_threadsafe(
                ctx.bot.send_message(user.id, "❌ Доступ не разрешён."),
                self.loop
            )
            win.destroy()

        # ------- кнопки -------
        frm = tk.Frame(win); frm.pack(pady=(12, 8))
        tk.Button(frm, text="Разрешить", width=12, bg="#90ee90", command=allow).pack(side="left", padx=8)
        tk.Button(frm, text="Отказать",   width=12, bg="#f08080", command=deny ).pack(side="right", padx=8)


    # ──────────────────────────────────────────────────────
    #  Иконка в системном трее + сворачивание/разворачивание
    # ──────────────────────────────────────────────────────
    def _on_close(self):
        """Свернуть окно в трей (повторный вызов — показать)."""
        if self.winfo_viewable():             # окно видно → прячем
            self.withdraw()
            if hasattr(self, "tray_icon"):
                self.tray_icon.visible = True
        else:                                 # окно скрыто → показываем
            if hasattr(self, "tray_icon"):
                self.tray_icon.visible = False
            self.deiconify()
            self.after(0, self.lift)

    def _create_tray_icon(self):
        """Создаёт pystray-иконку и запускает её в отдельном потоке."""
        def on_show(icon, item): self.after(0, self.deiconify)
        def on_hide(icon, item): self.after(0, self.withdraw)
        def on_quit(icon, item):
            icon.stop()
            self.after(0, self.destroy)

        img = Image.new("RGB", (64, 64), (106, 13, 173))
        ImageDraw.Draw(img).ellipse((16, 16, 48, 48), fill=(255, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Показать", on_show),
            pystray.MenuItem("Скрыть",   on_hide),
            pystray.MenuItem("Выход",    on_quit),
        )
        self.tray_icon = pystray.Icon("AIFA_MAX", img, "AIFA_MAX", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    # ──────────────────────────────────────────────────────
    #  Исправленный переключатель «Одним именем»
    # ──────────────────────────────────────────────────────
    def _set_one_name(self, state: bool):
        """Переключает режим «Одним именем» и обновляет вид кнопок."""
        self.one_name_mode       = state
        self.current_series_name = ""
        self.series_counter      = 1

        if state:          # ON  – левая кнопка зелёная
            self.btn_one_on .config(relief="sunken", bg="#90ee90")
            self.btn_one_off.config(relief="raised", bg="white")
            self._status("🔗 Режим одного имени включён")
        else:              # OFF – правая кнопка красная
            self.btn_one_off.config(relief="sunken", bg="#f08080")
            self.btn_one_on .config(relief="raised", bg="white")
            self._status("❌ Режим одного имени выключен")

        
    # ---------- вычисление π ----------
    def _generate_pi(self, digits: int = 1000) -> str:
        getcontext().prec = digits + 10
        pi, k = Decimal(0), 0
        while k < digits:
            pi += (Decimal(1)/(16**k))*(
                Decimal(4)/(8*k+1) - Decimal(2)/(8*k+4) -
                Decimal(1)/(8*k+5) - Decimal(1)/(8*k+6))
            k += 1
        return str(+pi)[:digits+2]


    # ---------- блок «пути сохранения» ----------
    def _build_paths(self):
        y = 70
        for key, label in (("photo_dir","📷 Foto"), ("video_dir","🎞️ Video"), ("doc_dir","📄 Doc")):
            tk.Button(self.canvas, text=label, font=("Segoe UI",10,"bold"),
                      command=lambda k=key: self._choose_dir(k))\
                .place(x=40, y=y, width=140, height=28)
            lbl = tk.Label(self.canvas, text=self.cfg[key], anchor="w", bg="white", fg="black", font=("Segoe UI",8))
            lbl.place(x=190, y=y+4, width=280, height=20)
            setattr(self, f"lbl_{key}", lbl)
            y += 40

    def _choose_dir(self, key: str):
        folder = filedialog.askdirectory()
        if folder:
            self.cfg[key] = folder
            save_cfg(self.cfg)
            getattr(self, f"lbl_{key}").config(text=folder)

    # ---------- статус, токены, AI-переключатели ----------
    def _build_status(self):
        self.lbl_status = tk.Label(self.canvas, text="❌ Бот не запущен", fg="black", font=("Segoe UI",11,"bold"))
        self.lbl_status.place(x=40, y=200)
        self.lbl_fname  = tk.Label(self.canvas, text="Имя файла: —",    fg="black", font=("Segoe UI",10,"bold"))
        self.lbl_fname.place(x=40, y=230)
        self.lbl_tokens = tk.Label(self.canvas, text="Токены: 0",       fg="black", font=("Segoe UI",10,"bold"))
        self.lbl_tokens.place(x=40, y=260)
        tk.Button(self.canvas, text="↻ Сброс токенов", bg="#d98cff", font=("Segoe UI",9,"bold"),
                  command=self._reset_tokens).place(x=200, y=256, width=140, height=24)

    def _reset_tokens(self):
        self.tokens = 0; self.total_rubles = 0.0
        self.lbl_tokens.config(text="Токены: 0")
        self.lbl_rubles.config(text="Стоимость: 0.00 ₽")

    def _build_ai_switch(self):
        x, y = 350, 180
        tk.Label(self.canvas, text="AI режим", fg="black", font=("Segoe UI",10,"bold")).place(x=x, y=y)
        self.btn_on  = tk.Button(self.canvas, text="On",  width=4, command=lambda: self._set_ai(True))
        self.btn_off = tk.Button(self.canvas, text="Off", width=4, command=lambda: self._set_ai(False))
        self.btn_on.place(x=x, y=y+30); self.btn_off.place(x=x+50, y=y+30)
        self._set_ai(True)

    def _set_ai(self, state: bool):
        self.ai = state
        self.btn_on .config(relief="sunken" if state else "raised", bg="#90ee90" if state else "white")
        self.btn_off.config(relief="raised" if state else "sunken", bg="white" if state else "#f08080")

    def _build_one_name_switch(self):
        x, y = 350, 250
        tk.Label(self.canvas, text="Одним именем", fg="black", font=("Segoe UI",10,"bold")).place(x=x, y=y)
        self.btn_one_on  = tk.Button(self.canvas, text="On",  width=4, command=lambda: self._set_one_name(True))
        self.btn_one_off = tk.Button(self.canvas, text="Off", width=4, command=lambda: self._set_one_name(False))
        self.btn_one_on.place(x=x, y=y+30); self.btn_one_off.place(x=x+50, y=y+30)
        self._set_one_name(False)


    # ---------- стоимость токенов ----------
    def _build_currency_display(self):
        self.lbl_rubles = tk.Label(self.canvas, text="Стоимость: 0.00 ₽", fg="black", font=("Segoe UI",10,"bold"))
        self.lbl_rubles.place(x=40, y=290)
        self.update_currency()      # первый запуск

    def update_currency(self):
        try:
            usd_rate = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=5).json()["Valute"]["USD"]["Value"]
            usd_cost = (self.tokens/1_000_000) * self.cfg.get("token_price_usd", 0.15)
            rub_cost = usd_cost * usd_rate
            self.total_rubles = rub_cost
            self.lbl_rubles.config(text=f"Стоимость: {rub_cost:.2f} ₽ (≈{usd_cost:.4f} $)")
        except Exception as e:
            log.warning(f"Ошибка запроса курса USD: {e}")
            self.lbl_rubles.config(text="Ошибка курса")

    # ---------- утилиты ----------
    def _uniq(self, path: Path) -> Path:
        if not path.exists(): return path
        stem, ext, i = path.stem, path.suffix, 1
        while True:
            cand = path.with_name(f"{stem}_{i}{ext}")
            if not cand.exists(): return cand
            i += 1

    def reset_series_name(self):
        self.current_series_name, self.series_counter = "", 1
        self._status("⏳ Имя серии сброшено по таймауту.")

    # ---------- π / OpenAI-heartbeat ----------
    def _update_pi(self):
        if not self.openai_ok:
            text = "Нет связи с нейросетью"
        elif not self.conn:
            text = "⚠ Нет связи"
        else:
            self._pi_idx = (self._pi_idx + 1) % len(self.PI)
            head = self.PI[self._pi_idx:self._pi_idx+self.MAX_PI_WIDTH]
            if len(head) < self.MAX_PI_WIDTH:
                head = self.PI[:self.MAX_PI_WIDTH-len(head)] + head
            text = "π = " + head
        self.lbl_pi.config(text=text)
        self.after(120, self._update_pi)

    def _check_openai(self):
        try:
            self.openai_ok = requests.get("https://api.openai.com/v1/models",
                                          headers={"Authorization": f"Bearer {OPENAI_KEY}"}, timeout=3).ok
        except Exception:
            self.openai_ok = False
        self.after(5000, self._check_openai)
    # ---------- меню «О боте» ----------
    def _open_about_menu(self):
        
        win = tk.Toplevel(self)
        win.title("О боте")
        win.geometry("280x140")
        win.transient(self)
        win.grab_set()
        win.configure(bg=self.ui_color_light)
        
        btn_instr = tk.Button(
            win,
            text="Инструкция",
            width=25,
            command=self._show_instruction,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_instr.pack(pady=(15, 5))

        btn_contact = tk.Button(
            win,
            text="💬 Связь с разработчиком",
            width=25,
            command=self._contact_developer_input,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_contact.pack(pady=5)

        btn_support = tk.Button(
            win,
            text="💖 Поддержать проект",
            width=25,
            command=self._show_support,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_support.pack(pady=5)


# ────────────────────────────────────────────────────────────────
#  Окно «Инструкция»
# ────────────────────────────────────────────────────────────────
    def _show_instruction(self):
        # вместо messagebox — своё окно, чтобы можно было стилизовать
        win = tk.Toplevel(self)
        win.title("Инструкция")
        win.geometry("500x1000")
        win.transient(self); win.grab_set()
        win.configure(bg=self.ui_color_light)
   
        text = (
            "Дорогой пользователь! Рад, что ты тестируешь мою программу!\n"
            "Моя программа называется AI File Assistant Max.\n\n"
            "    Программа для переноса файлов с телефона на ПК.\n"
            "            Telegram -------- Windows PC.\n\n"
            "1• В главном окне программы\n"
            " выбери папки для сохранения и режим работы.\n\n"
            "2• В Telegram найди бота @AIFA_MAX_XXX_BOT и отправь команду /start.\n"
            "3• В главном окне программы появится запрос на допуск — разреши.\n\n"
            "4• Перешли в чат свой файл (фото, видео, документ) — \n"
            "бот сохранит его и предложит имя.\n\n"
            "5• Оцени предложенное имя цифрой от 1 до 10:\n"
            "    - 6–10 — имя принимается.\n"
            "    - 1–5  — бот будет предлагать новые варианты,\n"
            "пока не получит оценку больше 5.\n"
            "        — вводя цифру ≤5, можешь добавить комментарии —\n"
            "нейросеть обязательно их учтёт!\n\n"
            "Твои оценки и комментарии обучают нейросеть —\n"
            "помогают AI-ассистенту лучше понимать твои предпочтения.\n\n"
            "Если нейросеть не справляется — нажми 0 и введи своё имя.\n"
            "Если есть конкретная задумка, в настройках есть кнопка промта.\n"
            "\nРежимы работы:\n"
            "      • AI режим On/Off —\n"
            "автоматическая или ручная генерация имени.\n"
            "      • «Одним именем» On/Off —\n"
            "единый префикс для серии файлов или отдельные имена.\n\n"
            "💰 Стоимость — ведётся подсчёт потраченных токенов.\n"
            "    ↻ «Сброс токенов» — обнуление счётчика и стоимости.\n\n"
            ">>> Если ты тестируешь бота, то сейчас пользуешься им\n"
            "абсолютно бесплатно! 😊\n\n"
            "📈 Бегущая строка π — статус работы бота:\n"
            "        π в движении — всё работает.\n"
            "        π остановилась — потеряна связь с Telegram.\n"
            "        π пропала — нет связи с OpenAI.\n\n"
            "🔧 Кнопка «Настройки» — открывает меню редактирования промта для имён,\n"
            "позволяет выбрать модель OpenAI, управлять белым списком пользователей\n"
            "и настраивать цветовую схему интерфейса.\n\n"
            "📸 Кнопка «Анализ фото» — запускает диалог загрузки изображения,\n"
            "предлагает ввести пользовательский промт, отправляет фото (base64) в GPT-4o\n"
            "и выводит подробное текстовое описание.\n\n"
            "\n        Приятного использования AIFA_MAX! 🚀\n"
            "\nP.S. Фотографии — это наша память. Не дай себе забыть!"
        )

        lbl = tk.Label(
            win,
            text=text,
            justify="left",
            bg=self.ui_color_light,
            fg="black",
            font=("Segoe UI", 9)
        )
        lbl.pack(fill="both", expand=True, padx=10, pady=10)

        btn_ok = tk.Button(
            win,
            text="Закрыть",
            command=win.destroy,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_ok.pack(pady=(0,10))

# ────────────────────────────────────────────────────────────────
#  Окно «Связь с разработчиком»
# ────────────────────────────────────────────────────────────────
    def _contact_developer_input(self):
        win = tk.Toplevel(self)
        win.title("Связь с разработчиком")
        win.geometry("350x220")
        win.transient(self); win.grab_set()
        win.configure(bg=self.ui_color_light)

        tk.Label(
            win,
            text="Сообщение:",
            font=("Segoe UI",10),
            bg=self.ui_color_light,
            fg="black"
        ).pack(anchor="w", padx=10, pady=(10,0))

        txt = tk.Text(
            win,
            height=8,
            width=40,
            bg="white",
            fg="black",
            relief="solid"
        )
        txt.pack(padx=10, pady=5)

        def send():
            msg = txt.get("1.0", tk.END).strip()
            if not msg:
                return messagebox.showwarning("Пусто", "Введите текст")
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                params={"chat_id": CREATOR_CHAT_ID, "text": msg}
            )
            if r.status_code == 200:
                messagebox.showinfo("Результат", "Отправлено")
                win.destroy()
            else:
                messagebox.showerror("Ошибка", "Не удалось отправить")

        btn_send = tk.Button(
            win,
            text="Отправить",
            width=12,
            command=send,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_send.pack(pady=(5,10))


# ────────────────────────────────────────────────────────────────
#  Окно «Поддержать проект»
# ────────────────────────────────────────────────────────────────
    def _show_support(self):
        win = tk.Toplevel(self)
        win.title("Поддержать проект")
        win.geometry("450x250")
        win.transient(self); win.grab_set()
        win.configure(bg=self.ui_color_light)

        # данные для отбивки
        support_data = [
            ("Российские карты:",  ["₽ Сбер: **** **** **** ****", "₽ Тинькофф: **** **** **** ****"]),
            ("Долларовые карты:",  ["💵 VISA-USD: **** **** **** ****"]),
            ("Криптовалюта:",      ["₿ BTC: 1Fx4fgqZzvMHgZRvvRZGNWD7ckbWN9E3E58e7Ca", "💠 USDT (ERC-20): 0x09cdeA91938f19513AB557C462599e9E3E58e7Ca"])
        ]

        for head, body in support_data:
            lbl_head = tk.Label(
                win,
                text=head,
                font=("Segoe UI",10,"bold"),
                bg=self.ui_color_light,
                fg="black"
            )
            lbl_head.pack(anchor="w", padx=10, pady=(10,0))

            for line in body:
                lbl_line = tk.Label(
                    win,
                    text="• " + line,
                    bg=self.ui_color_light,
                    fg="black"
                )
                lbl_line.pack(anchor="w", padx=20)

        btn_close = tk.Button(
            win,
            text="Закрыть",
            command=win.destroy,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_close.pack(pady=15)

        try:
            user = self.last_user
            who  = f"{user.id}/{user.first_name or ''} @{user.username}" if user else "неизвестно"
            asyncio.run_coroutine_threadsafe(
                self.app.bot.send_message(
                    CREATOR_CHAT_ID,
                    f"🔔 [GUI] Пользователь {who} нажал «Поддержать»",
                    disable_notification=True
                ),
                self.loop
            )
        except Exception as e:
            log.error(f"Не удалось отправить support-уведомление: {e}")



    def _not_ready(self):
        messagebox.showinfo("⏳", "Этот раздел ещё в разработке.")
        
    # ────────────────────────────────────────────────────────────────
    #  Меню «Настройки»
    # ────────────────────────────────────────────────────────────────
    def _open_settings_menu(self):
        win = tk.Toplevel(self)
        win.title("Настройки")
        win.geometry("300x240")
        win.transient(self)
        win.grab_set()
        # окрасим фон в светлую тему
        win.configure(bg=self.ui_color_light)

        tk.Label(
            win,
            text="Разделы:",
            font=("Segoe UI", 10, "bold"),
            bg=self.ui_color_light,
            fg="black"
        ).pack(pady=(10, 5))

        items = [
            ("Промт для названий", self._open_naming_prompt_settings),
            ("AI / OpenAI",    self._open_ai_settings),
            ("Доступ",         self._open_access_settings),
            ("Цветовая схема", self._interface_settings),
        ]
        for text, cmd in items:
            btn = tk.Button(
                win,
                text=text,
                width=25,
                command=cmd,
                bg=self.ui_color,
                fg="white",
                activebackground=self.ui_color_light,
                relief="flat"
            )
            btn.pack(pady=4)
        

    # ────────────────────────────────────────────────────────────────
    #  Настройки AI / OpenAI – выбор модели GPT
    # ────────────────────────────────────────────────────────────────
    def _open_ai_settings(self):
        win = tk.Toplevel(self)
        win.title("AI / OpenAI")
        win.geometry("280x160")
        win.transient(self); win.grab_set()
        win.configure(bg=self.ui_color_light)  # фон окна

        # Заголовок
        tk.Label(
            win,
            text="Выберите модель GPT:",
            font=("Segoe UI", 10, "bold"),
            bg=self.ui_color_light,
            fg="black"
        ).pack(pady=(10, 6))

        # OptionMenu
        models = ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4-turbo", "gpt-4o"]
        opt = tk.OptionMenu(win, self.openai_model_var, *models)
        opt.config(
            width=18,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        # меню самого OptionMenu
        opt["menu"].config(
            bg=self.ui_color_light,
            fg="black"
        )
        opt.pack(pady=5)

        # Кнопка Сохранить
        def save_and_close():
            global OPENAI_MODEL
            OPENAI_MODEL = self.openai_model_var.get()
            self.cfg["openai_model"] = OPENAI_MODEL
            save_cfg(self.cfg)
            messagebox.showinfo("Готово", f"Модель сохранена: {OPENAI_MODEL}")
            win.destroy()

        btn_save = tk.Button(
            win,
            text="Сохранить",
            width=14,
            command=save_and_close,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_save.pack(pady=(10, 8))



    # ────────────────────────────────────────────────────────────────
    #  Меню «Доступ» – управление белым списком
    # ────────────────────────────────────────────────────────────────
    def _open_access_settings(self):
        win = tk.Toplevel(self)
        win.title("Доступ")
        win.geometry("420x320")
        win.transient(self)
        win.grab_set()
        # фон окна
        win.configure(bg=self.ui_color_light)

        # ---------- поиск ----------
        tk.Label(
            win,
            text="Поиск:",
            font=("Segoe UI", 10, "bold"),
            bg=self.ui_color_light,
            fg="black"
        ).pack(anchor="w", padx=10, pady=(10,0))

        search_var = tk.StringVar()
        ent = tk.Entry(
            win,
            textvariable=search_var,
            bg="white",
            fg="black",
            relief="solid"
        )
        ent.pack(fill="x", padx=10, pady=(0,6))

        # ---------- таблица ----------
        cols = ("id","name","login")
        style = ttk.Style()
        style.configure(
            "Access.Treeview",
            background="white",
            fieldbackground="white",
            foreground="black"
        )
        style.configure(
            "Access.Treeview.Heading",
            background=self.ui_color,
            foreground="white"
        )
        tree = ttk.Treeview(
            win,
            columns=cols,
            show="headings",
            height=10,
            style="Access.Treeview"
        )
        for c, w in zip(cols, (120,180,90)):
            tree.heading(c, text=c.upper())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=10)

        data = self.cfg.get("allowed_users", [])
        def refresh_table(filter_txt: str = ""):
            tree.delete(*tree.get_children())
            q = filter_txt.lower()
            for u in data:
                if (q in str(u["id"]).lower() or
                    q in u.get("name","").lower() or
                    q in u.get("login","").lower()):
                    tree.insert(
                        "",
                        "end",
                        values=(u["id"], u.get("name",""), u.get("login",""))
                    )

        search_var.trace_add("write",
            lambda *a: refresh_table(search_var.get().strip())
        )
        refresh_table()

        # ---------- кнопки ----------
        frm = tk.Frame(win, bg=self.ui_color_light)
        frm.pack(pady=8)

        def add_user():
            dlg = tk.Toplevel(win)
            dlg.title("Добавить")
            dlg.geometry("280x180")
            dlg.transient(win)
            dlg.grab_set()
            dlg.configure(bg=self.ui_color_light)

            tk.Label(
                dlg, text="Telegram ID:", bg=self.ui_color_light, fg="black"
            ).grid(row=0, column=0, sticky="e", padx=6, pady=4)
            tk.Label(
                dlg, text="Имя Фамилия:", bg=self.ui_color_light, fg="black"
            ).grid(row=1, column=0, sticky="e", padx=6, pady=4)
            tk.Label(
                dlg, text="@логин:", bg=self.ui_color_light, fg="black"
            ).grid(row=2, column=0, sticky="e", padx=6, pady=4)

            id_var, name_var, log_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
            tk.Entry(dlg, textvariable=id_var, bg="white", fg="black", relief="solid")\
                .grid(row=0, column=1, padx=6)
            tk.Entry(dlg, textvariable=name_var, bg="white", fg="black", relief="solid")\
                .grid(row=1, column=1, padx=6)
            tk.Entry(dlg, textvariable=log_var, bg="white", fg="black", relief="solid")\
                .grid(row=2, column=1, padx=6)

            def ok():
                try:
                    uid = int(id_var.get())
                except ValueError:
                    return messagebox.showerror("Ошибка","ID должен быть числом")
                if any(u["id"]==uid for u in data):
                    return messagebox.showwarning("Уже есть","Такой ID уже добавлен")
                data.append({
                    "id": uid,
                    "name": name_var.get().strip(),
                    "login": log_var.get().strip()
                })
                self._save_allowed_users(data)
                refresh_table(search_var.get())
                dlg.destroy()

            btn_ok = tk.Button(
                dlg,
                text="OK",
                command=ok,
                width=10,
                bg=self.ui_color,
                fg="white",
                activebackground=self.ui_color_light,
                relief="flat"
            )
            btn_ok.grid(row=3, column=0, columnspan=2, pady=10)

        def remove_selected():
            sel = tree.selection()
            if not sel:
                return
            vid = tree.item(sel[0])["values"][0]
            if messagebox.askyesno("Удалить","Убрать выбранного пользователя?"):
                data[:] = [u for u in data if u["id"]!=vid]
                self._save_allowed_users(data)
                refresh_table(search_var.get())

        btn_add = tk.Button(
            frm,
            text="＋ Добавить",
            width=14,
            command=add_user,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_add.pack(side="left", padx=4)

        btn_remove = tk.Button(
            frm,
            text="✖ Удалить",
            width=14,
            command=remove_selected,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_remove.pack(side="left", padx=4)


    # ---------- меню «Анализ фото» ----------
    def _open_photo_menu(self):
        win = tk.Toplevel(self)
        win.title("Анализ фото")
        win.geometry("700x600")
        win.transient(self)
        win.grab_set()
        win.configure(bg=self.ui_color_light)

        # Переменные состояния
        self.photo_path_var = tk.StringVar(value="")
        self.prompt_var = tk.StringVar(value="")

        # Загрузка фото
        def load_photo():
            path = filedialog.askopenfilename(
                filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")])
            if path:
                self.photo_path_var.set(path)
                lbl_photo.config(text=f"Файл загружен: {Path(path).name}")

        # Запуск анализа через OpenAI
        async def generate_description_async(photo_path, prompt):
            try:
                with open(photo_path, "rb") as img_file:
                    response = await client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"}
                                }
                            ]}
                        ],
                        max_tokens=300
                    )
                    return response.choices[0].message.content.strip()
            except Exception as e:
                log.error(f"Ошибка анализа фото: {e}")
                return f"Ошибка анализа фото: {e}"

        def generate_description():
            photo_path = self.photo_path_var.get()
            prompt = self.prompt_var.get()
        
            if not photo_path:
                messagebox.showwarning("Ошибка", "Сначала загрузите фото.")
                return
        
            txt_output.delete("1.0", tk.END)
            txt_output.insert(tk.END, "⏳ Анализ фото...")

            async def run_and_display():
                description = await generate_description_async(photo_path, prompt)
                txt_output.delete("1.0", tk.END)
                txt_output.insert(tk.END, description)

            asyncio.run(run_and_display())

        # GUI компоненты
        # GUI компоненты
        btn_load = tk.Button(
            win,
            text="📂 Загрузить фото",
            command=load_photo,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_load.pack(pady=10)

        lbl_photo = tk.Label(
            win,
            text="Файл не загружен",
            bg=self.ui_color_light,
            fg="blue"
        )
        lbl_photo.pack()

        lbl_prompt = tk.Label(
            win,
            text="Введите промт:",
            bg=self.ui_color_light,
            fg="black"
        )
        lbl_prompt.pack(pady=5)

        entry_prompt = tk.Entry(
            win,
            textvariable=self.prompt_var,
            width=50,
            bg="white",
            fg="black",
            relief="solid"
        )
        entry_prompt.pack(pady=5)

        btn_generate = tk.Button(
            win,
            text="✨ Получить описание",
            command=generate_description,
            bg=self.ui_color,
            fg="white",
            activebackground=self.ui_color_light,
            relief="flat"
        )
        btn_generate.pack(pady=10)

        lbl_desc = tk.Label(
            win,
            text="Описание:",
            bg=self.ui_color_light,
            fg="black"
        )
        lbl_desc.pack(pady=5)

        txt_output = tk.Text(
            win,
            height=10,
            wrap="word",
            bg="white",
            fg="black"
        )
        txt_output.pack(expand=True, fill="both", padx=10, pady=10)
        
        
    def _open_naming_prompt_settings(self):
        win = tk.Toplevel(self)
        win.title("Промт для названий")
        win.geometry("350x180")
        win.transient(self); win.grab_set()
        win.configure(bg=self.ui_color_light)

        tk.Label(win,
                 text="Введите промт для генерации имён файлов:",
                 font=("Segoe UI",10,"bold"),
                 bg=self.ui_color_light,
                 fg="black").pack(pady=(15,5))

        prompt_var = tk.StringVar(value=self.cfg.get("naming_prompt",""))
        entry = tk.Entry(win,
                         textvariable=prompt_var,
                         width=40,
                         bg="white",
                         fg="black",
                         relief="solid")
        entry.pack(pady=5)

        def save():
            p = prompt_var.get().strip()
            self.cfg["naming_prompt"] = p
            save_cfg(self.cfg)
            messagebox.showinfo("Готово", f"Промт сохранён:\n«{p or '— (использовать по умолчанию)'}»")
            win.destroy()

        btn = tk.Button(win,
                        text="Сохранить",
                        width=12,
                        command=save,
                        bg=self.ui_color,
                        fg="white",
                        activebackground=self.ui_color_light,
                        relief="flat")
        btn.pack(pady=(10,10))
        
                
    # ---------- поток Telegram-бота ----------
    def _bot_thread(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop(); self.loop = loop
        try:
            app = ApplicationBuilder().token(TOKEN).build()
            loop.run_until_complete(verify_token(app.bot))
            self.app = app

            app.bot_data.update({"gui": self, "cfg": self.cfg})
            app.add_handler(CommandHandler("start",  self._cmd_start))
            app.add_handler(CommandHandler("about",  self._cmd_about))
            app.add_handler(CallbackQueryHandler(self._support_callback, pattern="^support_project$"))

            file_filter = filters.Document.ALL | filters.PHOTO | filters.VIDEO
            app.add_handler(MessageHandler(file_filter, self._handle_file))
            rating_re = r"^\s*(?:0|[1-9]|10)[).,]?\s*.*$"
            app.add_handler(MessageHandler(filters.Regex(rating_re), self._handle_rating))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_messages))

            self._status("🚀 Подключаюсь…")
            loop.run_until_complete(app.initialize())
            loop.run_until_complete(app.start())
            loop.run_until_complete(app.updater.start_polling())   # PTB ≤v20
            self.conn = True
            self._status("🟢 Бот запущен")
            loop.run_forever()
        except Exception as exc:
            log.exception("Bot error", exc_info=exc)
            self.conn = False
            self._status("🔴 Ошибка бота")
    # ---------- /start ----------
    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start с интерактивным запросом доступа."""
        user = update.effective_user
        self.last_user = user                            # запоминаем

        # 1) уведомляем администратора
        await ctx.bot.send_message(
            CREATOR_CHAT_ID,
            f"🔔 [START] {user.mention_html()} нажал /start",
            parse_mode="HTML",
            disable_notification=True
        )

        # 2) пользователь уже в белом списке — пускаем сразу
        if user.id in self.allowed_users:
            await update.message.reply_text(
                "👋 Привет! Пришли файл — я сохраню и предложу имя."
            )
            return

        # 3) пользователь НЕ в списке — запрашиваем решение через GUI
        await update.message.reply_text(
            "⏳ Запрос отправлен администратору. Ожидайте решения."
        )

        # открываем модальное окно одобрения / отказа в GUI-потоке
        self.after(
            0,
            lambda: self._request_access_dialog(user, update, ctx)
        )

    # ---------- /about ----------
    async def _cmd_about(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user; self.last_user = user
       
        if update.effective_user.id not in self.allowed_users:
            return await update.message.reply_text("❌ У вас нет доступа к боту.")



        keyboard = [[InlineKeyboardButton("💖 Поддержать проект", callback_data="support_project")]]
        await update.message.reply_text("AI File Assistant Max. Нажмите кнопку ниже:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- callback «support_project» ----------
    async def _support_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.callback_query.answer("Спасибо за поддержку!")
        await ctx.bot.send_message(
            CREATOR_CHAT_ID, f"🔔 [SUPPORT] {user.id}/{user.full_name} нажал кнопку поддержки", disable_notification=True
        )

    # ---------- приём файлов ----------
    async def _handle_file(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id not in self.allowed_users:
            return await update.message.reply_text("❌ У вас нет доступа к боту.")

        msg = update.message
        if msg.document:
            file_obj, dir_key, ext = msg.document, "doc_dir", Path(msg.document.file_name).suffix or ""
        elif msg.photo:
            file_obj, dir_key, ext = msg.photo[-1], "photo_dir", ".jpg"
        else:
            file_obj, dir_key = msg.video, "video_dir"
            ext = Path(file_obj.file_name or "").suffix or ".mp4"

        tg_file = await file_obj.get_file()
        tmp_dir = Path(self.cfg[dir_key])
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"tmp_{uuid4().hex}{ext}"
        await tg_file.download_to_drive(str(tmp_path))

        basename = Path(getattr(file_obj, "file_name", "") or file_obj.file_unique_id).stem
        fid = file_obj.file_unique_id
        self.last_file_id = fid

        # 1) AI On, Одним именем On
        if self.ai and self.one_name_mode:
            self.pending_series_files.append(tmp_path)
            if len(self.pending_series_files) == 1:
                # запомним URL и оригинальный basename+ext для серии
                self.series_image_url = tg_file.file_path
                self.series_basename_ext = basename + ext

                default_prompt = self.series_basename_ext
                prompt_to_use  = self.cfg.get("naming_prompt") or default_prompt
                name, tokens = await gpt_name(
                    prompt=prompt_to_use,
                    image_url=self.series_image_url                
                )
                self._addtok(tokens)
                self.current_series_name = name or basename
                await update.message.reply_text(
                    f"✔️ Предлагаю имя серии: <b>{self.current_series_name}</b>\n"
                    "Оцените 1-10 (≤5 — ещё вариант, 0 — своё имя):",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("➕ Файл добавлен в серию.")
            return

        # 2) AI On, Одним именем Off
        if self.ai and not self.one_name_mode:
            
            # выбираем промт: пользовательский или дефолтный basename+ext
            default_prompt = basename + ext
            prompt_to_use  = self.cfg.get("naming_prompt") or default_prompt
            name, tokens = await gpt_name(
                prompt=prompt_to_use,
                image_url=tg_file.file_path
            )
            
            self._addtok(tokens)
            out_path = self._uniq(tmp_path.with_name(f"{name or basename}{ext}"))
            tmp_path.rename(out_path)
            self.last_out_path = out_path
            await update.message.reply_text(
                f"✔️ Предлагаю имя: <b>{out_path.name}</b>\n"
                "Оцените 1-10 (≤5 — ещё вариант, 0 — своё имя):",
                parse_mode="HTML"
            )
            return

        # 3) AI Off, Одним именем On
        if not self.ai and self.one_name_mode:
            self.pending_series_files.append(tmp_path)
            if len(self.pending_series_files) == 1:
                self.waiting_manual_name[update.effective_chat.id] = {
                    "series": True,
                    "ext": ext,
                    "default_name": basename
                }
                await update.message.reply_text(
                    f"✏️ Введите имя серии или '-' чтобы оставить техническое: ({basename})"
                )
            else:
                await update.message.reply_text("➕ Файл добавлен в серию.")
            return

        # 4) AI Off, Одним именем Off
        self.waiting_manual_name[update.effective_chat.id] = {
            "series": False,
            "path": tmp_path,
            "ext": ext,
            "default_name": basename
        }
        await update.message.reply_text(
            f"✏️ Введите имя файла или '-' чтобы оставить техническое: ({basename})"
        )
 

 
    # ---------- таймаут оценки ----------
    async def _rating_timeout(self, chat_id: int):
        try:
            await self.app.bot.send_message(chat_id, f"⌛ Время вышло, имя сохранено:\n<b>{self.last_out_path.name}</b>", parse_mode="HTML")
        except Exception as e:
            log.error(f"Timeout-msg error: {e}")
        finally:
            self.rating_timer = None

    # ---------- обработка оценки ----------
    async def _handle_rating(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id not in self.allowed_users:
            return await update.message.reply_text("❌ У вас нет доступа к боту.")

        m = re.match(r"^\s*(0|[1-9]|10)[).,]?\s*(.*)$", update.message.text.strip())
        if not m:
            return await update.message.reply_text("⚠️ Введите оценку 0–10.")
        rate, hint = int(m.group(1)), m.group(2).strip()

        fid = self.last_file_id
        if fid:
            self.name_history.setdefault(fid, []).append({"rating": rate, "comment": hint})
            save_name_history(self.name_history)

        # AI Off — рейтинг не влияет
        if not self.ai:
            return

        # 1) AI On, Одним именем On
        if self.one_name_mode:
            if rate == 0:
                self.waiting_manual_name[update.effective_chat.id] = {
                    "series": True,
                    "ext": self.pending_series_files[0].suffix,
                    "default_name": self.current_series_name
                }
                await update.message.reply_text("✏️ Введите своё имя серии:")
                return

            if rate >= 6:
                base = self.current_series_name
                for i, path in enumerate(self.pending_series_files, 1):
                    new_path = self._uniq(path.with_name(f"{base} {i}{path.suffix}"))
                    path.rename(new_path)
                self.pending_series_files.clear()
                self.current_series_name = ""
                await update.message.reply_text(
                    f"✅ Серия принята под именем: <b>{base}</b>",
                    parse_mode="HTML"
                )
                return

            # 1-5: новое имя на основе оригинального изображения
            prev = [
                {"name": e["name"], "rating": e["rating"], "comment": e.get("comment","")}
                for e in self.name_history.get(fid, []) if e.get("name")
            ]
            new_name, tokens = await gpt_name(
                prompt=hint,
                image_url=self.series_image_url,
                variant=2,
                prev_names=prev
            )
            self._addtok(tokens)
            self.current_series_name = new_name or self.current_series_name
            await update.message.reply_text(
                f"🔄 Предлагаю другое имя серии: <b>{self.current_series_name}</b>\n"
                "Оцените снова 1-10:",
                parse_mode="HTML"
            )
            return

        # 2) AI On, Одним именем Off
        if not self.one_name_mode:
            if rate == 0:
                self.waiting_manual_name[update.effective_chat.id] = {
                    "series": False,
                    "path": self.last_out_path,
                    "ext": self.last_out_path.suffix,
                    "default_name": self.last_out_path.stem
                }
                await update.message.reply_text("✏️ Введите своё имя файла:")
                return
            if rate >= 6:
                await update.message.reply_text(
                    f"✅ Имя принято: <b>{self.last_out_path.name}</b>",
                    parse_mode="HTML"
                )
                return
            prev = [
                {"name": e["name"], "rating": e["rating"], "comment": e.get("comment","")}
                for e in self.name_history.get(fid, []) if e.get("name")
            ]
            new_name, tokens = await gpt_name(
                prompt=hint,
                image_url=self.last_out_path.as_uri(),
                variant=2,
                prev_names=prev
            )
            self._addtok(tokens)
            new_path = self._uniq(self.last_out_path.with_name(f"{new_name}{self.last_out_path.suffix}"))
            self.last_out_path.rename(new_path)
            self.last_out_path = new_path
            await update.message.reply_text(
                f"🔄 Попробуем: <b>{new_path.name}</b>\nОцените снова 1-10:",
                parse_mode="HTML"
            )
            return



    async def _handle_text_messages(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        if user.id not in self.allowed_users:
            return await update.message.reply_text("❌ У вас нет доступа к боту.")

        txt = update.message.text.strip()
        if chat_id in self.waiting_manual_name:
            info = self.waiting_manual_name.pop(chat_id)

            # Серийный ввод (AI Off или ручной для серии)
            if info["series"]:
                base = info["default_name"] if txt == "-" else re.sub(r"\s+", " ", txt)[:50]
                for i, path in enumerate(self.pending_series_files, 1):
                    new_path = self._uniq(path.with_name(f"{base} {i}{info['ext']}"))
                    path.rename(new_path)
                self.pending_series_files.clear()
                self.current_series_name = ""
                await update.message.reply_text(
                    f"✅ Серия сохранена под именем: <b>{base}</b>",
                    parse_mode="HTML"
                )
                return

            # Одиночный ввод (AI Off, OneName Off или рейтинг 0)
            path = info["path"]
            base = info["default_name"] if txt == "-" else re.sub(r"\s+", " ", txt)[:50]
            new_path = self._uniq(path.with_name(f"{base}{info['ext']}"))
            path.rename(new_path)
            self.last_out_path = new_path
            self._fname(new_path.name)
            await update.message.reply_text(
                f"✅ Имя сохранено: <b>{new_path.name}</b>",
                parse_mode="HTML"
            )
            return

        # Всё остальное
        await update.message.reply_text("ℹ️ Сообщение получено.")



            # ═══════════════════════════════════════════════════════════════
    #  Настройки интерфейса  → выбор цвета через colorchooser
    # ═══════════════════════════════════════════════════════════════
    def _interface_settings(self):
        """
        Позволяет выбрать основной цвет интерфейса.
        После выбора сохраняет его в config.json
        и мгновенно перерисовывает градиент.
        """
        # запрашиваем цвет
        rgb, hex_code = colorchooser.askcolor(
            title="Выберите основной цвет", initialcolor=self.ui_color
        )
        if not hex_code:                 # пользователь нажал Cancel
            return

        # сохраняем новый цвет и «осветлённую» версию
        self.ui_color = hex_code
        self.ui_color_light = mix_color(hex_code, "#ffffff", 0.5)

        # обновляем градиент
        self._redraw_gradient()

        # пишем в конфиг
        self.cfg["ui_color"] = self.ui_color
        self.cfg["ui_color_light"] = self.ui_color_light
        save_cfg(self.cfg)

    # --- перерисовка существующих прямоугольников градиента --------
    def _redraw_gradient(self):
        if not hasattr(self, "gradient_rects"):
            return
        steps = len(self.gradient_rects) - 1 or 1
        for i, rid in enumerate(self.gradient_rects):
            color = mix_color(self.ui_color, self.ui_color_light, i / steps)
            self.canvas.itemconfig(rid, fill=color)


    # ---------- GUI-helpers ----------
    def _status(self, txt: str): self.after(0, lambda: self.lbl_status.config(text=txt))
    def _fname (self, n: str):   self.after(0, lambda: self.lbl_fname .config(text=f"Имя файла: {n}"))
    def _addtok(self, n: int):
        if n: self.tokens += n; self.after(0, lambda: self.lbl_tokens.config(text=f"Токены: {self.tokens}")); self.update_currency()

# ────────────────────────────────────────────────────────────────
#  main()
# ────────────────────────────────────────────────────────────────
def main():
    asyncio.run(verify_token(Bot(token=TOKEN)))
    log.info("Запуск AIFA_MAX…")
    FancyGUI().mainloop()
    log.info("Завершение AIFA_MAX.")

if __name__ == "__main__":
    main()
