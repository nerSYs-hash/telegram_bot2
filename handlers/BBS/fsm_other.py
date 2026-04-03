#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSM раздела BBS «Другое»: барахолка, аренда, услуги, помощь.
Один активный бот-месседж во время заполнения + HTML-превью и публикация в BBS thread.
"""

import html
import json
import logging
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)

import asyncio

from handlers.BBS.helpers_bbs import city_to_hashtag
from handlers.BBS.database_bbs import get_other_post
from utils.helpers import get_moscow_time


OTHER_STATE_CATEGORY = 'other_category'
OTHER_STATE_CITY = 'other_city'
OTHER_STATE_CITY_INPUT = 'other_city_input'
OTHER_STATE_AUTHOR = 'other_author'
OTHER_STATE_TITLE = 'other_title'
OTHER_STATE_DESCRIPTION = 'other_description'
OTHER_STATE_PRICE = 'other_price'
OTHER_STATE_MEDIA = 'other_media'

MAX_OTHER_MEDIA = 4

AUTHOR_NAME_REGEX = re.compile(r'^[A-Za-zА-Яа-яЁё\s\-]{2,30}$')
PHONE_REGEX = re.compile(r'(?<!\w)(?:\+?\d[\d\s\-()]{5,20}\d)(?!\w)')

OTHER_CATEGORY_OPTIONS = {
    'rent': {
        'label': 'Аренда/Недвижимость',
        'emoji': '🏠',
        'tags': ['#Аренда', '#Недвижимость'],
    },
    'market': {
        'label': 'Продам/Куплю',
        'emoji': '📦',
        'tags': ['#Продам_Куплю', '#Барахолка'],
    },
    'free': {
        'label': 'Отдам даром',
        'emoji': '🎁',
        'tags': ['#Отдам_Даром'],
    },
    'services': {
        'label': 'Услуги/Работа',
        'emoji': '🛠',
        'tags': ['#Услуги', '#Работа'],
    },
    'help': {
        'label': 'Помощь',
        'emoji': '🆘',
        'tags': ['#Помощь'],
    },
}

OTHER_CITY_PRESETS = [
    ('Москва', '#Мск'),
    ('Санкт-Петербург', '#Спб'),
    ('Онлайн / Любой', '#Онлайн'),
]

OTHER_EDITABLE_FIELDS = {
    'category': '📦 Категория',
    'city': '🏙 Город',
    'author_name': '👤 Имя автора',
    'title': '📝 Заголовок',
    'description': '🛡 Описание',
    'price': '💰 Цена / Условия',
    'media': '🎞 Фото / Видео',
}


def get_other_state(context):
    return context.user_data.get('other_state')


def set_other_state(context, state):
    context.user_data['other_state'] = state


def get_other_data(context):
    if 'other_data' not in context.user_data:
        context.user_data['other_data'] = {
            'category': None,
            'city': None,
            'author_name': None,
            'title': None,
            'description': None,
            'price': None,
            'media': [],
        }
    return context.user_data['other_data']


def clear_other(context):
    for key in (
        'other_state', 'other_data', 'other_bot_msg_id', 'other_preview_message_ids',
        'other_control_msg_id', 'other_editing_field',
    ):
        context.user_data.pop(key, None)


def contains_phone_number(text: str) -> bool:
    for match in PHONE_REGEX.finditer(text or ''):
        digits = re.sub(r'\D', '', match.group(0))
        if 7 <= len(digits) <= 11:
            return True
    return False


def is_other_editing(context) -> bool:
    return bool(context.user_data.get('other_editing_field'))


def set_other_editing(context, field_name: str | None):
    if field_name:
        context.user_data['other_editing_field'] = field_name
    else:
        context.user_data.pop('other_editing_field', None)


def build_other_tags(data: dict) -> list[str]:
    tags = []
    category = OTHER_CATEGORY_OPTIONS.get(data.get('category'))
    if category:
        tags.extend(category['tags'])
    city = data.get('city')
    if city:
        tags.append(city)
    return tags


def build_other_tags_line(data: dict) -> str:
    tags = build_other_tags(data)
    if not tags:
        return ''
    return f"🏷 <b>Автохештеги:</b> {' '.join(tags)}"


def compose_other_step_text(step_header: str, body: str, data: dict) -> str:
    tags_line = build_other_tags_line(data)
    if not tags_line:
        return f'{step_header}\n\n{body}'
    return f'{step_header}\n\n{body}\n\n{tags_line}'


def get_other_back_callback(context, normal_callback: str) -> str:
    return 'other_edit_start' if is_other_editing(context) else normal_callback


def build_other_post_text(data: dict) -> str:
    category = OTHER_CATEGORY_OPTIONS.get(data.get('category'), OTHER_CATEGORY_OPTIONS['market'])
    category_label = html.escape(category['label'])
    category_emoji = category['emoji']
    city = html.escape(data.get('city') or '#Онлайн')
    title = html.escape(data.get('title') or '')
    author_name = html.escape(data.get('author_name') or '')
    description = html.escape(data.get('description') or '')
    price = html.escape(data.get('price') or 'Не указано')
    tags = category['tags'] + ([data.get('city')] if data.get('city') else [])
    tags_line = ' '.join(tags)

    text = (
        f"{category_emoji} <b>[{category_label}]</b> {city}\n"
        f"<b>{title}</b>\n\n"
        f"👤 <b>Автор:</b> {author_name}\n"
        f"📝 <b>Описание:</b> {description}\n"
        f"💰 <b>Цена/Условия:</b> {price}\n\n"
        f"{tags_line}\n"
        f"✉️ <i>Связь через личные сообщения.</i>"
    )
    return text


def build_other_buttons(user_id: int, bot_username: str | None):
    row = [InlineKeyboardButton('💌 Написать автору', url=f'tg://user?id={user_id}')]
    if bot_username:
        row.append(
            InlineKeyboardButton(
                '⚠️ Пожаловаться',
                url=f'https://t.me/{bot_username}?start=report_{user_id}',
            )
        )
    return InlineKeyboardMarkup([row])


def build_other_preview_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton('✅ Опубликовать', callback_data='other_publish'),
            InlineKeyboardButton('✏️ Редактировать', callback_data='other_edit_start'),
        ],
        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
    ])


def build_other_edit_keyboard(data: dict) -> InlineKeyboardMarkup:
    rows = []
    for field_name, label in OTHER_EDITABLE_FIELDS.items():
        suffix = ''
        if field_name == 'category' and data.get('category'):
            suffix = f" · {OTHER_CATEGORY_OPTIONS[data['category']]['emoji']}"
        elif field_name == 'city' and data.get('city'):
            suffix = f" · {data['city']}"
        elif field_name == 'media':
            suffix = f" · {len(data.get('media', []))}/{MAX_OTHER_MEDIA}"
        elif data.get(field_name):
            suffix = ' · заполнено'
        rows.append([InlineKeyboardButton(f'{label}{suffix}', callback_data=f'other_edit_field_{field_name}')])

    rows.append([InlineKeyboardButton('🔙 К предпросмотру', callback_data='other_preview_back')])
    rows.append([InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')])
    return InlineKeyboardMarkup(rows)


async def _safe_delete_message(bot, chat_id: int, message_id: int | None):
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _cleanup_preview_messages(context, chat_id: int):
    for message_id in context.user_data.pop('other_preview_message_ids', []):
        await _safe_delete_message(context.bot, chat_id, message_id)


async def _replace_other_message(src, context, text, keyboard_rows):
    markup = InlineKeyboardMarkup(keyboard_rows)

    if hasattr(src, 'edit_message_text'):
        await _cleanup_preview_messages(context, src.message.chat.id)
        await src.edit_message_text(text=text, parse_mode='HTML', reply_markup=markup)
        context.user_data['other_bot_msg_id'] = src.message.message_id
        return

    chat_id = src.chat.id
    try:
        await src.delete()
    except Exception:
        pass

    await _cleanup_preview_messages(context, chat_id)

    message_id = context.user_data.get('other_bot_msg_id')
    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=markup,
            )
            return
        except Exception:
            pass

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup=markup,
    )
    context.user_data['other_bot_msg_id'] = msg.message_id


def _build_category_keyboard(selected=None, back_callback: str | None = None):
    keyboard = []
    for category_id, meta in OTHER_CATEGORY_OPTIONS.items():
        check = '✅ ' if selected == category_id else ''
        keyboard.append([
            InlineKeyboardButton(
                f"{check}{meta['emoji']} {meta['label']}",
                callback_data=f'other_category_{category_id}',
            )
        ])
    if back_callback:
        keyboard.append([InlineKeyboardButton('🔙 Назад', callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')])
    return keyboard


def _build_city_keyboard(selected=None, back_callback: str = 'other_back_to_category'):
    keyboard = []
    for title, tag in OTHER_CITY_PRESETS:
        check = '✅ ' if selected == tag else ''
        keyboard.append([
            InlineKeyboardButton(f'{check}{title}', callback_data=f'other_city_{tag}')
        ])
    keyboard.append([InlineKeyboardButton('🏙 Свой вариант', callback_data='other_city_custom')])
    keyboard.append([InlineKeyboardButton('🔙 Назад', callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')])
    return keyboard


def _build_price_keyboard(back_callback: str = 'other_back_to_description'):
    return [
        [InlineKeyboardButton('🆓 Бесплатно', callback_data='other_price_free')],
        [InlineKeyboardButton('🔄 Договорная / Обмен', callback_data='other_price_deal')],
        [InlineKeyboardButton('🔙 Назад', callback_data=back_callback)],
        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
    ]


def _build_media_keyboard(has_media: bool, media_count: int, back_callback: str = 'other_back_to_price'):
    keyboard = []
    if has_media:
        keyboard.append([InlineKeyboardButton('✅ Готово', callback_data='other_media_done')])
    else:
        keyboard.append([InlineKeyboardButton('⏭ Без фото/видео', callback_data='other_media_skip')])
    keyboard.append([InlineKeyboardButton('🔙 Назад', callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')])
    if media_count >= MAX_OTHER_MEDIA:
        keyboard.insert(0, [InlineKeyboardButton('✅ Лимит достигнут', callback_data='other_media_done')])
    return keyboard


async def show_other_rules(query, context, db):
    clear_other(context)
    rules_text = (
        '📦 <b>Доска объявлений Pulse (Раздел «Другое»)</b>\n'
        'Здесь мы не ищем любовь, а решаем дела!\n\n'
        'Сдаете комнату для своих? Продаете приставку? Ищете работу, классного мастера '
        'или просто хотите попросить комьюнити о помощи? Вам сюда.\n\n'
        '🚨 <b>ПРАВИЛА БЕЗОПАСНОСТИ:</b>\n'
        '• Никаких номеров телефонов. Во избежание спама и мошенничества публикация личных '
        'номеров строго запрещена. Пусть вам пишут прямо в ЛС Телеграма.\n'
        '• Модерация. Любой скам, незаконные товары или коммерческая реклама без согласования '
        'приведут к мгновенному удалению объявления.\n'
        '• Цензура. Фото и видео должны быть без обнаженки, эротики, шок-контента и незаконного контента.\n\n'
        'Всё кристально ясно? Тогда жмите кнопку ниже и создавайте объявление! 👇'
    )
    await query.edit_message_text(
        rules_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ Согласен', callback_data='other_rules_agree')],
            [InlineKeyboardButton('❌ Не согласен', callback_data='other_rules_decline')],
        ]),
    )
    return True


async def show_other_landing(query, context, db):
    if not db.is_feature_enabled('bbs_other'):
        await query.answer('📦 Раздел «Другое» сейчас отключён.', show_alert=True)
        return True

    clear_other(context)
    text = (
        '📦 <b>Pulse BBS: Другое</b>\n\n'
        'Объявления по аренде, услугам, продаже, обмену и помощи внутри комьюнити.\n\n'
        'Перед заполнением бот покажет короткие правила безопасности и затем откроет анкету.'
    )
    buttons = [
        [InlineKeyboardButton('📝 Создать объявление', callback_data='other_create_start')],
    ]
    existing_post = get_other_post(db, query.from_user.id)
    if existing_post:
        buttons.append([InlineKeyboardButton('🗑 Удалить моё объявление', callback_data='other_delete_confirm')])
    buttons.append([InlineKeyboardButton('🔙 Назад', callback_data='menu_bbs')])
    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return True


async def start_other_category_step(src, context):
    set_other_state(context, OTHER_STATE_CATEGORY)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '📦 <b>Шаг 1/7 — Категория</b>',
            'Выберите раздел объявления. Категорийные хештеги добавятся автоматически.',
            get_other_data(context),
        ),
        _build_category_keyboard(
            get_other_data(context).get('category'),
            'other_edit_start' if is_other_editing(context) else None,
        ),
    )


async def start_other_city_step(src, context):
    set_other_state(context, OTHER_STATE_CITY)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '🏙 <b>Шаг 2/7 — Город</b>',
            'Выберите город из списка или введите свой вариант. Для ручного ввода используется тот же словарь городов РФ, что и в основном BBS.',
            get_other_data(context),
        ),
        _build_city_keyboard(
            get_other_data(context).get('city'),
            get_other_back_callback(context, 'other_back_to_category'),
        ),
    )


async def start_other_author_step(src, context):
    set_other_state(context, OTHER_STATE_AUTHOR)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '👤 <b>Шаг 3/7 — Имя автора</b>',
            'Введите имя: только буквы, от 2 до 30 символов.',
            get_other_data(context),
        ),
        [
            [InlineKeyboardButton('🔙 Назад', callback_data=get_other_back_callback(context, 'other_back_to_city'))],
            [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
        ],
    )


async def start_other_title_step(src, context):
    set_other_state(context, OTHER_STATE_TITLE)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '📝 <b>Шаг 4/7 — Заголовок</b>',
            'Кратко опишите объявление. До 50 символов.',
            get_other_data(context),
        ),
        [
            [InlineKeyboardButton('🔙 Назад', callback_data=get_other_back_callback(context, 'other_back_to_author'))],
            [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
        ],
    )


async def start_other_description_step(src, context):
    set_other_state(context, OTHER_STATE_DESCRIPTION)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '🛡 <b>Шаг 5/7 — Описание</b>',
            'Опишите объявление до 500 символов.\nТелефоны, номера WhatsApp/Telegram и другие номера в тексте запрещены.',
            get_other_data(context),
        ),
        [
            [InlineKeyboardButton('🔙 Назад', callback_data=get_other_back_callback(context, 'other_back_to_title'))],
            [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
        ],
    )


async def start_other_price_step(src, context):
    set_other_state(context, OTHER_STATE_PRICE)
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '💰 <b>Шаг 6/7 — Цена / Условия</b>',
            'Введите цену текстом или выберите готовый вариант.',
            get_other_data(context),
        ),
        _build_price_keyboard(get_other_back_callback(context, 'other_back_to_description')),
    )


async def start_other_media_step(src, context):
    set_other_state(context, OTHER_STATE_MEDIA)
    media_count = len(get_other_data(context).get('media', []))
    body = (
        f'Можно загрузить до {MAX_OTHER_MEDIA} файлов: фото, видео или смешанный набор.\n'
        'Примеры: 4 фото, 4 видео, 1 видео + 3 фото, 3 видео + 1 фото.\n'
        f'📎 Загружено: {media_count}/{MAX_OTHER_MEDIA}'
    )
    if is_other_editing(context):
        body = (
            'Загрузите новый набор медиа. Старый набор будет полностью заменён.\n'
            + body
        )
    await _replace_other_message(
        src,
        context,
        compose_other_step_text(
            '🎞 <b>Шаг 7/7 — Фото / Видео</b>',
            body,
            get_other_data(context),
        ),
        _build_media_keyboard(
            media_count > 0,
            media_count,
            get_other_back_callback(context, 'other_back_to_price'),
        ),
    )


async def _send_preview_media(context, chat_id: int, media_items: list, caption: str):
    preview_ids = []
    try:
        if len(media_items) == 1:
            item = media_items[0]
            if item['type'] == 'video':
                msg = await context.bot.send_video(
                    chat_id=chat_id,
                    video=item['file_id'],
                    caption=caption,
                    parse_mode='HTML',
                )
            else:
                msg = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=item['file_id'],
                    caption=caption,
                    parse_mode='HTML',
                )
            preview_ids.append(msg.message_id)
        elif len(media_items) > 1:
            media_group = []
            for index, item in enumerate(media_items):
                kwargs = {'media': item['file_id']}
                if index == 0:
                    kwargs['caption'] = caption
                    kwargs['parse_mode'] = 'HTML'
                media_group.append(
                    InputMediaVideo(**kwargs) if item['type'] == 'video' else InputMediaPhoto(**kwargs)
                )
            messages = await context.bot.send_media_group(chat_id=chat_id, media=media_group)
            preview_ids.extend(msg.message_id for msg in messages)
    except Exception as exc:
        logging.error(f'BBS Other preview media error: {exc}')
    return preview_ids


async def show_other_preview(src, context):
    data = get_other_data(context)
    chat_id = src.message.chat.id if hasattr(src, 'message') else src.chat.id
    text = build_other_post_text(data)
    caption = f'👀 <b>ПРЕДПРОСМОТР</b>\n\n{text}'

    old_msg_id = context.user_data.pop('other_bot_msg_id', None)
    if old_msg_id:
        await _safe_delete_message(context.bot, chat_id, old_msg_id)

    if not hasattr(src, 'message'):
        try:
            await src.delete()
        except Exception:
            pass

    await _cleanup_preview_messages(context, chat_id)
    media_items = data.get('media', [])
    if media_items:
        context.user_data['other_preview_message_ids'] = await _send_preview_media(
            context, chat_id, media_items, caption
        )
    else:
        preview_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode='HTML',
        )
        context.user_data['other_preview_message_ids'] = [preview_msg.message_id]

    control_msg = await context.bot.send_message(
        chat_id=chat_id,
        text='👆 Всё верно? Если да, публикуем объявление.',
        reply_markup=build_other_preview_controls(),
    )
    context.user_data['other_bot_msg_id'] = control_msg.message_id
    set_other_editing(context, None)


async def show_other_preview_controls_only(query, context):
    await query.edit_message_text(
        '👆 Всё верно? Если да, публикуем объявление.',
        reply_markup=build_other_preview_controls(),
    )


async def show_other_edit_menu(query, context):
    await query.edit_message_text(
        '✏️ <b>Редактирование объявления</b>\n\nВыберите, что нужно изменить перед публикацией.',
        parse_mode='HTML',
        reply_markup=build_other_edit_keyboard(get_other_data(context)),
    )


async def delete_other_post_messages(bot, db, post, target_chat_id):
    message_ids = post.get('message_ids') or '[]'
    if isinstance(message_ids, str):
        try:
            message_ids = json.loads(message_ids)
        except Exception:
            message_ids = []

    for message_id in message_ids or []:
        await _safe_delete_message(bot, target_chat_id, message_id)

    try:
        db.cursor.execute('DELETE FROM bbs_other_posts WHERE id = ?', (post['id'],))
        db.conn.commit()
    except Exception as exc:
        logging.error(f'BBS Other delete db error: {exc}')


async def publish_other_post(query, context, db, target_chat_id, bbs_thread_id):
    user = query.from_user
    data = get_other_data(context)
    text = build_other_post_text(data)
    media_items = data.get('media', [])
    bot_username = context.bot.username
    sent_message_ids = []

    old_post = get_other_post(db, user.id)
    if old_post:
        await delete_other_post_messages(context.bot, db, old_post, target_chat_id)

    try:
        if len(media_items) == 1:
            item = media_items[0]
            send_kwargs = {
                'chat_id': target_chat_id,
                'message_thread_id': bbs_thread_id,
                'caption': text,
                'parse_mode': 'HTML',
                'reply_markup': build_other_buttons(user.id, bot_username),
            }
            if item['type'] == 'video':
                msg = await context.bot.send_video(video=item['file_id'], **send_kwargs)
            else:
                msg = await context.bot.send_photo(photo=item['file_id'], **send_kwargs)
            sent_message_ids.append(msg.message_id)
        elif len(media_items) > 1:
            media_group = []
            for index, item in enumerate(media_items):
                kwargs = {'media': item['file_id']}
                if index == 0:
                    kwargs['caption'] = text
                    kwargs['parse_mode'] = 'HTML'
                media_group.append(
                    InputMediaVideo(**kwargs) if item['type'] == 'video' else InputMediaPhoto(**kwargs)
                )

            messages = await context.bot.send_media_group(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                media=media_group,
            )
            sent_message_ids.extend(msg.message_id for msg in messages)
            button_msg = await context.bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                text='� <b>Связаться с автором объявления</b>',
                parse_mode='HTML',
                reply_markup=build_other_buttons(user.id, bot_username),
            )
            sent_message_ids.append(button_msg.message_id)
        else:
            msg = await context.bot.send_message(
                chat_id=target_chat_id,
                message_thread_id=bbs_thread_id,
                text=text,
                parse_mode='HTML',
                reply_markup=build_other_buttons(user.id, bot_username),
            )
            sent_message_ids.append(msg.message_id)
    except Exception as exc:
        logging.error(f'BBS Other publish error: {exc}')
        await query.edit_message_text(
            f'❌ Ошибка публикации объявления: {html.escape(str(exc))}',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('🔙 В меню BBS', callback_data='menu_bbs')]
            ]),
        )
        clear_other(context)
        return

    now_iso = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
    try:
        db.cursor.execute(
            '''
            INSERT INTO bbs_other_posts
                (user_id, username, category, city, author_name, title, description, price,
                 photos, message_ids, thread_id, published_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                category=excluded.category,
                city=excluded.city,
                author_name=excluded.author_name,
                title=excluded.title,
                description=excluded.description,
                price=excluded.price,
                photos=excluded.photos,
                message_ids=excluded.message_ids,
                thread_id=excluded.thread_id,
                published_at=excluded.published_at
            ''',
            (
                user.id,
                user.username,
                data['category'],
                data['city'],
                data['author_name'],
                data['title'],
                data['description'],
                data['price'],
                json.dumps(media_items, ensure_ascii=False),
                json.dumps(sent_message_ids),
                bbs_thread_id,
                now_iso,
                now_iso,
            ),
        )
        db.conn.commit()
    except Exception as exc:
        logging.error(f'BBS Other db save error: {exc}')

    await _cleanup_preview_messages(context, query.message.chat.id)
    clear_other(context)
    await query.edit_message_text(
        '✅ <b>Объявление опубликовано!</b>\n\nОно уже появилось в ветке BBS.',
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('🔙 В меню BBS', callback_data='menu_bbs')]
        ]),
    )


async def handle_other_media_input(message, context):
    data = get_other_data(context)
    media_items = data.get('media', [])

    if len(media_items) >= MAX_OTHER_MEDIA:
        try:
            await message.delete()
        except Exception:
            pass
        await _replace_other_message(
            message,
            context,
            f'⚠️ Уже загружено {MAX_OTHER_MEDIA}/{MAX_OTHER_MEDIA} файлов. Лимит достигнут.',
            _build_media_keyboard(True, len(media_items)),
        )
        return True

    item = None
    if message.photo:
        item = {'type': 'photo', 'file_id': message.photo[-1].file_id}
    elif message.video:
        item = {'type': 'video', 'file_id': message.video.file_id}

    if not item:
        await _replace_other_message(
            message,
            context,
            '❌ На этом шаге принимаются только фото или видео.',
            _build_media_keyboard(
                bool(media_items),
                len(media_items),
                get_other_back_callback(context, 'other_back_to_price'),
            ),
        )
        return True

    media_items.append(item)
    data['media'] = media_items
    await _replace_other_message(
        message,
        context,
        compose_other_step_text(
            '🎞 <b>Шаг 7/7 — Фото / Видео</b>',
            f'📎 Загружено: {len(media_items)}/{MAX_OTHER_MEDIA}\nМожно отправить ещё файл или завершить публикацию.',
            data,
        ),
        _build_media_keyboard(
            True,
            len(media_items),
            get_other_back_callback(context, 'other_back_to_price'),
        ),
    )
    return True


async def process_other_input(message, context, db):
    state = get_other_state(context)
    if not state:
        return False

    try:
        text = (message.text or '').strip()
        editing = is_other_editing(context)

        if state == OTHER_STATE_CITY_INPUT:
            if not text or len(text) > 50:
                await _replace_other_message(
                    message,
                    context,
                    '❌ Введите город до 50 символов.',
                    [
                        [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_city')],
                        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                    ],
                )
                return True
            get_other_data(context)['city'] = city_to_hashtag(text)
            if editing:
                await show_other_preview(message, context)
            else:
                await start_other_author_step(message, context)
            return True

        if state == OTHER_STATE_AUTHOR:
            if not AUTHOR_NAME_REGEX.match(text):
                await _replace_other_message(
                    message,
                    context,
                    '❌ Имя должно содержать только буквы, пробел или дефис. Длина: 2-30 символов.',
                    [
                        [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_city')],
                        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                    ],
                )
                return True
            get_other_data(context)['author_name'] = text.title()
            if editing:
                await show_other_preview(message, context)
            else:
                await start_other_title_step(message, context)
            return True

        if state == OTHER_STATE_TITLE:
            if not text or len(text) > 50:
                await _replace_other_message(
                    message,
                    context,
                    f'❌ Заголовок должен быть от 1 до 50 символов. Сейчас: {len(text)}.',
                    [
                        [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_author')],
                        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                    ],
                )
                return True
            get_other_data(context)['title'] = text
            if editing:
                await show_other_preview(message, context)
            else:
                await start_other_description_step(message, context)
            return True

        if state == OTHER_STATE_DESCRIPTION:
            if not text or len(text) > 500:
                await _replace_other_message(
                    message,
                    context,
                    f'❌ Описание должно быть от 1 до 500 символов. Сейчас: {len(text)}.',
                    [
                        [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_title')],
                        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                    ],
                )
                return True
            if contains_phone_number(text):
                await _replace_other_message(
                    message,
                    context,
                    '🚫 В описании найден номер телефона. Уберите номер и оставьте связь только через ЛС Telegram.',
                    [
                        [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_title')],
                        [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                    ],
                )
                return True
            get_other_data(context)['description'] = text
            if editing:
                await show_other_preview(message, context)
            else:
                await start_other_price_step(message, context)
            return True

        if state == OTHER_STATE_PRICE:
            if not text or len(text) > 80:
                await _replace_other_message(
                    message,
                    context,
                    '❌ Укажите цену или условия до 80 символов.',
                    _build_price_keyboard(),
                )
                return True
            get_other_data(context)['price'] = text
            if editing:
                await show_other_preview(message, context)
            else:
                await start_other_media_step(message, context)
            return True

        if state == OTHER_STATE_MEDIA:
            return await handle_other_media_input(message, context)

    except Exception as exc:
        logging.error(f'BBS Other input error: {exc}')
        try:
            await message.reply_text('❌ Ошибка обработки ввода. Попробуйте ещё раз.')
        except Exception:
            pass
        return True

    return False


async def handle_other_callback(query, context, db, target_chat_id, bbs_thread_id):
    data = query.data
    if data != 'bbs_other_stub' and not data.startswith('other_'):
        return False

    try:
        if data == 'bbs_other_stub':
            return await show_other_landing(query, context, db)

        if not db.is_feature_enabled('bbs_other'):
            await query.answer('📦 Раздел «Другое» сейчас отключён.', show_alert=True)
            return True

        if data == 'other_create_start':
            return await show_other_rules(query, context, db)

        if data == 'other_delete_confirm':
            await query.edit_message_text(
                '🗑 <b>Удаление объявления</b>\n\nВы уверены? Объявление будет удалено из ветки BBS и из базы данных.',
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('✅ Да, удалить', callback_data='other_delete_yes')],
                    [InlineKeyboardButton('🔙 Отмена', callback_data='bbs_other_stub')],
                ]),
            )
            return True

        if data == 'other_delete_yes':
            post = get_other_post(db, query.from_user.id)
            if post:
                await delete_other_post_messages(context.bot, db, post, target_chat_id)
                await query.edit_message_text(
                    '✅ Объявление удалено.',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton('🔙 В меню BBS', callback_data='menu_bbs')]
                    ]),
                )
            else:
                await query.answer('У вас нет активного объявления.', show_alert=True)
                await show_other_landing(query, context, db)
            return True

        if data == 'other_rules_agree':
            clear_other(context)
            await start_other_category_step(query, context)
            return True

        if data == 'other_rules_decline':
            await show_other_landing(query, context, db)
            return True

        if data == 'other_cancel':
            chat_id = query.message.chat.id
            await _cleanup_preview_messages(context, chat_id)
            clear_other(context)
            await query.edit_message_text(
                '❌ Создание объявления отменено.',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('🔙 В меню BBS', callback_data='menu_bbs')]
                ]),
            )
            return True

        if data.startswith('other_category_'):
            category = data.replace('other_category_', '')
            if category not in OTHER_CATEGORY_OPTIONS:
                await query.answer('❌ Неизвестная категория', show_alert=True)
                return True
            get_other_data(context)['category'] = category
            if is_other_editing(context):
                await show_other_preview(query, context)
            else:
                await start_other_city_step(query, context)
            return True

        if data.startswith('other_city_') and data != 'other_city_custom':
            city_tag = data.replace('other_city_', '')
            get_other_data(context)['city'] = city_tag
            if is_other_editing(context):
                await show_other_preview(query, context)
            else:
                await start_other_author_step(query, context)
            return True

        if data == 'other_city_custom':
            set_other_state(context, OTHER_STATE_CITY_INPUT)
            await _replace_other_message(
                query,
                context,
                '🏙 <b>Шаг 2/7 — Свой город</b>\n\nВведите город текстом.',
                [
                    [InlineKeyboardButton('🔙 Назад', callback_data='other_back_to_city')],
                    [InlineKeyboardButton('❌ Отмена', callback_data='other_cancel')],
                ],
            )
            return True

        if data == 'other_price_free':
            get_other_data(context)['price'] = 'Бесплатно'
            if is_other_editing(context):
                await show_other_preview(query, context)
            else:
                await start_other_media_step(query, context)
            return True

        if data == 'other_price_deal':
            get_other_data(context)['price'] = 'Договорная / Обмен'
            if is_other_editing(context):
                await show_other_preview(query, context)
            else:
                await start_other_media_step(query, context)
            return True

        if data == 'other_media_skip':
            get_other_data(context)['media'] = []
            await show_other_preview(query, context)
            return True

        if data == 'other_media_done':
            await show_other_preview(query, context)
            return True

        if data == 'other_publish':
            await publish_other_post(query, context, db, target_chat_id, bbs_thread_id)
            return True

        if data == 'other_edit_start':
            await show_other_edit_menu(query, context)
            return True

        if data == 'other_preview_back':
            await show_other_preview_controls_only(query, context)
            return True

        if data.startswith('other_edit_field_'):
            field_name = data.replace('other_edit_field_', '')
            if field_name not in OTHER_EDITABLE_FIELDS:
                await query.answer('❌ Неизвестное поле', show_alert=True)
                return True

            set_other_editing(context, field_name)
            if field_name == 'category':
                await start_other_category_step(query, context)
            elif field_name == 'city':
                await start_other_city_step(query, context)
            elif field_name == 'author_name':
                await start_other_author_step(query, context)
            elif field_name == 'title':
                await start_other_title_step(query, context)
            elif field_name == 'description':
                await start_other_description_step(query, context)
            elif field_name == 'price':
                await start_other_price_step(query, context)
            elif field_name == 'media':
                get_other_data(context)['media'] = []
                await start_other_media_step(query, context)
            return True

        back_map = {
            'other_back_to_category': start_other_category_step,
            'other_back_to_city': start_other_city_step,
            'other_back_to_author': start_other_author_step,
            'other_back_to_title': start_other_title_step,
            'other_back_to_description': start_other_description_step,
            'other_back_to_price': start_other_price_step,
        }
        if data in back_map:
            await back_map[data](query, context)
            return True

    except Exception as exc:
        logging.error(f'BBS Other callback error: {exc}')
        try:
            await query.answer('❌ Ошибка в разделе «Другое». Попробуйте ещё раз.', show_alert=True)
        except Exception:
            pass
        return True

    return False


async def republish_other_post(bot, db, post: dict, target_chat_id: int, bbs_thread_id: int) -> list[int]:
    """
    Перепубликует объявление раздела «Другое» в ветку BBS из данных БД.
    Возвращает список новых message_id. Обновляет message_ids в БД.
    """
    # Восстанавливаем данные из БД для build_other_post_text
    data = {
        'category': post.get('category'),
        'city': post.get('city'),
        'author_name': post.get('author_name'),
        'title': post.get('title'),
        'description': post.get('description'),
        'price': post.get('price'),
        'media': [],
    }

    # Парсим медиа из поля photos
    raw_photos = post.get('photos', '[]')
    if isinstance(raw_photos, str):
        try:
            media_items = json.loads(raw_photos)
        except Exception:
            media_items = []
    else:
        media_items = raw_photos or []

    text = build_other_post_text(data)
    user_id = post['user_id']
    bot_username = bot.username
    sent_ids = []

    if len(media_items) == 1:
        item = media_items[0]
        send_kwargs = {
            'chat_id': target_chat_id,
            'message_thread_id': bbs_thread_id,
            'caption': text,
            'parse_mode': 'HTML',
            'reply_markup': build_other_buttons(user_id, bot_username),
        }
        if item.get('type') == 'video':
            msg = await bot.send_video(video=item['file_id'], **send_kwargs)
        else:
            msg = await bot.send_photo(photo=item['file_id'], **send_kwargs)
        sent_ids.append(msg.message_id)
    elif len(media_items) > 1:
        media_group = []
        for idx, item in enumerate(media_items):
            kwargs = {'media': item['file_id']}
            if idx == 0:
                kwargs['caption'] = text
                kwargs['parse_mode'] = 'HTML'
            media_group.append(
                InputMediaVideo(**kwargs) if item.get('type') == 'video' else InputMediaPhoto(**kwargs)
            )
        messages = await bot.send_media_group(
            chat_id=target_chat_id,
            message_thread_id=bbs_thread_id,
            media=media_group,
        )
        sent_ids.extend(m.message_id for m in messages)
        btn_msg = await bot.send_message(
            chat_id=target_chat_id,
            message_thread_id=bbs_thread_id,
            text='👇 <b>Связаться с автором объявления</b>',
            parse_mode='HTML',
            reply_markup=build_other_buttons(user_id, bot_username),
        )
        sent_ids.append(btn_msg.message_id)
    else:
        msg = await bot.send_message(
            chat_id=target_chat_id,
            message_thread_id=bbs_thread_id,
            text=text,
            parse_mode='HTML',
            reply_markup=build_other_buttons(user_id, bot_username),
        )
        sent_ids.append(msg.message_id)

    # Обновляем message_ids в БД
    try:
        db.cursor.execute(
            'UPDATE bbs_other_posts SET message_ids = ?, thread_id = ? WHERE user_id = ?',
            (json.dumps(sent_ids), bbs_thread_id, user_id),
        )
        db.conn.commit()
    except Exception as exc:
        logging.error(f'BBS Other: ошибка обновления message_ids при перепубликации: {exc}')

    return sent_ids


async def restore_all_other_posts(bot, db, target_chat_id: int, bbs_thread_id: int) -> tuple[int, int]:
    """
    Перепубликует все объявления раздела «Другое» из БД в ветку.
    Возвращает (успешно, ошибок).
    """
    try:
        db.cursor.execute('SELECT * FROM bbs_other_posts')
        posts = [dict(row) for row in db.cursor.fetchall()]
    except Exception as exc:
        logging.error(f'BBS Other restore: ошибка чтения БД: {exc}')
        return 0, 0

    ok = 0
    errors = 0
    for post in posts:
        try:
            await republish_other_post(bot, db, post, target_chat_id, bbs_thread_id)
            ok += 1
        except Exception as exc:
            logging.error(f'BBS Other restore: ошибка перепубликации user_id={post.get("user_id")}: {exc}')
            errors += 1
        await asyncio.sleep(2)  # защита от FloodControl

    return ok, errors