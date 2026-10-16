"""Inline-клавиатуры для интерфейса бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import DEFAULT_SCALE


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Улучшить фото", callback_data="menu:enhance")],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help"),
            ],
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
        ]
    )


def enhance_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
        ]
    )


def photo_options_kb(default_scale: int = DEFAULT_SCALE) -> InlineKeyboardMarkup:
    mark_2 = " • по умолчанию" if default_scale == 2 else ""
    mark_4 = " • по умолчанию" if default_scale == 4 else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✨ Улучшить ×2{mark_2}", callback_data="enhance:2")],
            [InlineKeyboardButton(text=f"🚀 Улучшить ×4{mark_4}", callback_data="enhance:4")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="enhance:cancel")],
        ]
    )


def after_result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Улучшить ещё фото", callback_data="menu:enhance")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
        ]
    )


def settings_kb(current_scale: int) -> InlineKeyboardMarkup:
    mark_2 = " ✅" if current_scale == 2 else ""
    mark_4 = " ✅" if current_scale == 4 else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔍 Масштаб ×2{mark_2}", callback_data="settings:2")],
            [InlineKeyboardButton(text=f"🔍 Масштаб ×4{mark_4}", callback_data="settings:4")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
        ]
    )
