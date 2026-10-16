"""Telegram-бот AI Photo Enhancer на aiogram 3."""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
)

from config import LOG_LEVEL, MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, TELEGRAM_BOT_TOKEN
from image_processor import (
    EnhanceResult,
    ImageProcessingError,
    enhance_image,
    is_supported_filename,
    realesrgan_status,
)
from keyboards import (
    after_result_kb,
    enhance_prompt_kb,
    main_menu_kb,
    photo_options_kb,
    settings_kb,
)
from sessions import UserSession, ensure_temp_dir, store

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("photo_enhancer")

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать в AI Photo Enhancer.\n"
    "\n"
    "Я помогу улучшить качество твоих фотографий с помощью AI.\n"
    "\n"
    "✨ Что я умею:\n"
    "• Увеличивать разрешение\n"
    "• Повышать резкость\n"
    "• Уменьшать шум\n"
    "• Улучшать детализацию\n"
    "\n"
    "Выбери действие ниже 👇"
)

ENHANCE_PROMPT = (
    "📸 Отправь фотографию, которую хочешь улучшить.\n"
    "\n"
    "Поддерживаются JPG, PNG и WEBP."
)

HELP_TEXT = (
    "ℹ️ Помощь\n"
    "\n"
    "Как улучшить фото:\n"
    "1. Нажми «📸 Улучшить фото».\n"
    "2. Отправь изображение как фото или как файл (JPG, PNG, WEBP).\n"
    "3. Выбери масштаб: ×2 или ×4.\n"
    "4. Дождись обработки — бот пришлёт результат.\n"
    "\n"
    "⚙️ В «Настройках» можно выбрать масштаб по умолчанию. "
    "Он будет отмечен на кнопках после загрузки фото.\n"
    "\n"
    "Советы:\n"
    "• Для максимального качества отправляй снимок как файл, а не как сжатое фото.\n"
    "• PNG с прозрачностью сохраняется как PNG.\n"
    "• Слишком большие изображения могут быть отклонены, чтобы не перегрузить память.\n"
    "• Навигация работает кнопками — команды печатать не нужно, кроме /start."
)

SETTINGS_TEXT = "⚙️ Настройки обработки"


def _engine_caption(result: EnhanceResult) -> str:
    size_from = f"{result.original_size[0]}×{result.original_size[1]}"
    size_to = f"{result.output_size[0]}×{result.output_size[1]}"
    if result.used_ai:
        method = "обработано с помощью Real-ESRGAN (AI-апскейл)"
    else:
        method = (
            "обработано запасным алгоритмом OpenCV/Pillow "
            "(Real-ESRGAN сейчас недоступен)"
        )
    extra = ""
    if result.had_transparency:
        extra = "\nПрозрачность PNG сохранена."
    return (
        f"✅ Фото обработано.\n"
        f"Масштаб: ×{result.scale}\n"
        f"Размер: {size_from} → {size_to}\n"
        f"{method}.{extra}"
    )


async def _edit_or_send(callback: CallbackQuery, text: str, reply_markup) -> None:
    message = callback.message
    if message is None:
        if callback.from_user:
            await callback.bot.send_message(
                callback.from_user.id, text, reply_markup=reply_markup
            )
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        await store.reset_flow(message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def on_main_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user:
        await store.reset_flow(callback.from_user.id)
    await _edit_or_send(callback, WELCOME_TEXT, main_menu_kb())


@router.callback_query(F.data == "menu:enhance")
async def on_enhance_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user:
        session = await store.get(callback.from_user.id)
        session.processing = False
        await store.clear_photo(callback.from_user.id)
        session.waiting_for_photo = True
    await _edit_or_send(callback, ENHANCE_PROMPT, enhance_prompt_kb())


@router.callback_query(F.data == "menu:settings")
async def on_settings(callback: CallbackQuery) -> None:
    await callback.answer()
    scale = 2
    if callback.from_user:
        session = await store.get(callback.from_user.id)
        scale = session.scale
    await _edit_or_send(callback, SETTINGS_TEXT, settings_kb(scale))


@router.callback_query(F.data == "menu:help")
async def on_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit_or_send(callback, HELP_TEXT, enhance_prompt_kb())


@router.callback_query(F.data.in_({"settings:2", "settings:4"}))
async def on_settings_scale(callback: CallbackQuery) -> None:
    await callback.answer("Сохранено")
    if callback.from_user is None or callback.data is None:
        return
    scale = int(callback.data.split(":")[1])
    session = await store.get(callback.from_user.id)
    session.scale = scale
    await _edit_or_send(
        callback,
        f"{SETTINGS_TEXT}\n\nВыбран масштаб ×{scale} по умолчанию.",
        settings_kb(scale),
    )


@router.callback_query(F.data == "enhance:cancel")
async def on_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    if callback.from_user:
        await store.reset_flow(callback.from_user.id)
    await _edit_or_send(callback, WELCOME_TEXT, main_menu_kb())


@router.callback_query(F.data.in_({"enhance:2", "enhance:4"}))
async def on_enhance_scale(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    user_id = callback.from_user.id
    user_lock = await store.lock_for(user_id)
    if user_lock.locked():
        await callback.answer("Уже обрабатываю твоё фото, подожди немного.", show_alert=True)
        return

    async with user_lock:
        session = await store.get(user_id)
        if session.processing:
            await callback.answer("Обработка уже запущена.", show_alert=True)
            return
        if session.photo_path is None or not session.photo_path.exists():
            await callback.answer("Сначала отправь фотографию.", show_alert=True)
            session.waiting_for_photo = True
            await _edit_or_send(callback, ENHANCE_PROMPT, enhance_prompt_kb())
            return

        scale = int(callback.data.split(":")[1])
        session.processing = True
        await callback.answer()

        message = callback.message
        if message:
            try:
                await message.edit_text("⏳ Обрабатываю фотографию...")
            except Exception:
                await message.answer("⏳ Обрабатываю фотографию...")

        photo_path = session.photo_path
        job_dir = session.photo_job_dir or photo_path.parent
        output_ext = ".png" if photo_path.suffix.lower() == ".png" else ".jpg"
        output_path = job_dir / f"enhanced_{uuid.uuid4().hex}{output_ext}"

        try:
            result = await asyncio.to_thread(enhance_image, photo_path, output_path, scale)
            await _send_result(callback, result)
        except ImageProcessingError as exc:
            logger.info("Ошибка обработки для пользователя %s: %s", user_id, exc)
            error_text = f"⚠️ {exc}"
            if message:
                try:
                    await message.edit_text(error_text, reply_markup=enhance_prompt_kb())
                except Exception:
                    await message.answer(error_text, reply_markup=enhance_prompt_kb())
        except Exception:
            logger.exception("Неожиданная ошибка обработки изображения")
            error_text = "⚠️ Не удалось обработать изображение. Попробуй другое фото."
            if message:
                try:
                    await message.edit_text(error_text, reply_markup=enhance_prompt_kb())
                except Exception:
                    await message.answer(error_text, reply_markup=enhance_prompt_kb())
        finally:
            session.processing = False
            await store.clear_photo(user_id)
            session.waiting_for_photo = False


async def _send_result(callback: CallbackQuery, result: EnhanceResult) -> None:
    caption = _engine_caption(result)
    data = result.output_path.read_bytes()
    filename = result.output_path.name
    photo = BufferedInputFile(data, filename=filename)
    chat_id = callback.message.chat.id if callback.message else callback.from_user.id

    send_as_document = (
        result.had_transparency
        or result.output_path.suffix.lower() == ".png"
        or len(data) > 9 * 1024 * 1024
    )
    try:
        if send_as_document:
            await callback.bot.send_document(
                chat_id,
                document=photo,
                caption=caption,
                reply_markup=after_result_kb(),
            )
        else:
            await callback.bot.send_photo(
                chat_id,
                photo=photo,
                caption=caption,
                reply_markup=after_result_kb(),
            )
    except Exception:
        logger.exception("Не удалось отправить результат как фото, пробую документ")
        await callback.bot.send_document(
            chat_id,
            document=BufferedInputFile(data, filename=filename),
            caption=caption,
            reply_markup=after_result_kb(),
        )

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_text("✅ Готово.")
            except Exception:
                pass


@router.message(F.photo)
async def on_photo(message: Message) -> None:
    if message.from_user is None or not message.photo:
        return
    photo = message.photo[-1]
    await _save_incoming_file(
        message=message,
        file_id=photo.file_id,
        file_size=photo.file_size,
        suggested_name="photo.jpg",
    )


@router.message(F.document)
async def on_document(message: Message) -> None:
    if message.from_user is None or message.document is None:
        return
    document = message.document
    name = document.file_name or "image"
    mime = (document.mime_type or "").lower()
    if not (is_supported_filename(name) or mime in {"image/jpeg", "image/png", "image/webp"}):
        await message.answer(
            "⚠️ Этот файл не поддерживается. Отправь JPG, PNG или WEBP.",
            reply_markup=enhance_prompt_kb(),
        )
        return
    if not is_supported_filename(name):
        ext = { "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime, ".jpg")
        name = f"image{ext}"
    await _save_incoming_file(
        message=message,
        file_id=document.file_id,
        file_size=document.file_size,
        suggested_name=name,
    )


@router.message(F.sticker | F.animation | F.video | F.video_note)
async def on_unsupported_media(message: Message) -> None:
    await message.answer(
        "⚠️ Я работаю только с изображениями JPG, PNG и WEBP.",
        reply_markup=enhance_prompt_kb(),
    )


@router.message()
async def on_other_text(message: Message) -> None:
    session = await store.get(message.from_user.id) if message.from_user else None
    if session and session.waiting_for_photo:
        await message.answer(
            "Пожалуйста, отправь изображение или нажми «Главное меню».",
            reply_markup=enhance_prompt_kb(),
        )
        return
    await message.answer(
        "Выбери действие на кнопках ниже — так удобнее.",
        reply_markup=main_menu_kb(),
    )


async def _save_incoming_file(
    message: Message,
    file_id: str,
    file_size: int | None,
    suggested_name: str,
) -> None:
    user_id = message.from_user.id if message.from_user else 0
    session = await store.get(user_id)

    if file_size and file_size > MAX_FILE_SIZE_BYTES:
        await message.answer(
            f"⚠️ Файл слишком большой. Максимум {MAX_FILE_SIZE_MB} МБ.",
            reply_markup=enhance_prompt_kb(),
        )
        return

    await store.clear_photo(user_id)
    session.waiting_for_photo = False

    job_dir = ensure_temp_dir() / f"user_{user_id}_{uuid.uuid4().hex}"
    job_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(suggested_name).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    input_path = job_dir / f"input{suffix}"

    try:
        tg_file = await message.bot.get_file(file_id)
        if tg_file.file_size and tg_file.file_size > MAX_FILE_SIZE_BYTES:
            await message.answer(
                f"⚠️ Файл слишком большой. Максимум {MAX_FILE_SIZE_MB} МБ.",
                reply_markup=enhance_prompt_kb(),
            )
            return
        await message.bot.download(tg_file, destination=input_path)
    except Exception:
        logger.exception("Не удалось скачать файл пользователя")
        await message.answer(
            "⚠️ Не удалось загрузить файл. Попробуй ещё раз.",
            reply_markup=enhance_prompt_kb(),
        )
        return

    session.photo_path = input_path
    session.photo_job_dir = job_dir
    session.waiting_for_photo = False

    await message.answer(
        "Фото получено. Выбери, как улучшить изображение:",
        reply_markup=photo_options_kb(session.scale),
    )


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не задан. Скопируй .env.example в .env и укажи токен.")
        sys.exit(1)

    ensure_temp_dir()
    ai_ok, ai_info = realesrgan_status()
    if ai_ok:
        logger.info("Real-ESRGAN доступен")
    else:
        logger.info("Real-ESRGAN недоступен (%s). Будет использован OpenCV/Pillow.", ai_info)

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Бот запущен. Ожидание обновлений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
