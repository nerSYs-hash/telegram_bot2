#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Экспорт полной статистики в PDF с поддержкой кириллицы и эмодзи.

Data Integrity: все числовые вычисления выполняются через Decimal.
В PDF-ячейки передаются отформатированные строки (это норма для PDF),
но входные данные сначала проходят через to_decimal() для корректного округления.
"""

import os
import traceback
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from utils.helpers.time_utils import get_moscow_time
from utils.helpers.formatting import to_decimal, round_decimal, format_number

# ── БЛОК РЕГИСТРАЦИИ ШРИФТОВ ────────────────────────────────

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def find_font(name):
    for folder in ['fonts', 'font']:
        path = os.path.join(base_dir, folder, name)
        if os.path.exists(path):
            return path
    return None

PATH_NORMAL = find_font('DejaVuSans.ttf')
PATH_BOLD   = find_font('DejaVuSans-Bold.ttf')
PATH_SYMB   = find_font('Symbola.ttf')

font_normal = 'Helvetica'
font_bold   = 'Helvetica-Bold'
font_symbol = None

if PATH_NORMAL:
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', PATH_NORMAL))
        font_normal = 'DejaVu'
        if PATH_BOLD:
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', PATH_BOLD))
            font_bold = 'DejaVu-Bold'
        else:
            font_bold = 'DejaVu'
    except Exception as e:
        print(f"[PDF] Ошибка DejaVu: {e}")

if PATH_SYMB:
    try:
        pdfmetrics.registerFont(TTFont('Symbola', PATH_SYMB))
        font_symbol = 'Symbola'
        print("[PDF] Symbola загружен")
    except Exception as e:
        print(f"[PDF] Ошибка Symbola: {e}")

styles = getSampleStyleSheet()
styles['Normal'].fontName = font_normal


ICONS_MAP = {
    '💎': 'diamond.png',
    '📊': 'chart.png',
    '🏆': 'trophy.png',
    '📅': 'calendar.png',
    '👤': 'user.png',
    '💬': 'chat.png',
    '🏦': 'bank.png',
    '🆕': 'new.png',
    '👋': 'left.png',
    '📊': 'er_icon.png',  # noqa: F601 — TODO: дубль emoji '📊', затирает первый (chart.png). Заменить на другой emoji
    '🛡️': 'health.png'
}

def fix_emojis(text):
    """Превращает текстовые эмодзи в теги картинок для PDF"""
    if not text:
        return text
    
    res = str(text)
    # Определяем путь к папке с иконками относительно корня
    # Настраиваем путь правильно (base_dir мы определили в начале файла)
    icons_dir = os.path.join(base_dir, 'assets', 'icons')

    for emoji, filename in ICONS_MAP.items():
        if emoji in res:
            img_path = os.path.join(icons_dir, filename)
            # Если файл существует, вставляем картинку
            if os.path.exists(img_path):
                # width и height — размер в PDF. 
                # valign='bottom' — чтобы иконка стояла на строке с текстом
                img_tag = f'<img src="{img_path}" width="12" height="12" valign="bottom"/>'
                res = res.replace(emoji, img_tag)
    
    return res


def mk_style(name, font_name_val=None, **kw):
    """Создатель стилей с поддержкой HTML-тегов (allowTags=1)."""
    f_name = font_name_val if font_name_val else font_normal
    return ParagraphStyle(name, parent=styles['Normal'], fontName=f_name, allowTags=1, **kw)


def _fmt_pdf(val, places: int = 2) -> str:
    """
    Форматирует число для PDF-ячейки через Decimal (без ошибок округления).
    Возвращает строку — в PDF это единственно возможный тип данных.
    """
    d = round_decimal(val, places)
    # Форматируем с пробелом как разделителем тысяч
    formatted = "{:,.{}f}".format(float(d), places).replace(',', ' ')
    return formatted


# ── ОСНОВНАЯ ФУНКЦИЯ ЭКСПОРТА ───────────────────────────────

def export_stats_to_pdf(stats_data, filename):
    try:
        C_HEADER  = colors.HexColor('#1a1a2e')
        C_ACCENT  = colors.HexColor('#7c5cfc')
        C_ACCENT2 = colors.HexColor('#2ecc8a')
        C_GOLD    = colors.HexColor('#f5c842')
        C_ROW_ODD = colors.HexColor('#f8f8ff')
        C_TEXT    = colors.HexColor('#1c1c26')
        C_WHITE   = colors.white

        s_title    = mk_style('Title2',    fontSize=22, textColor=C_WHITE,  alignment=TA_CENTER, font_name_val=font_bold, spaceAfter=4)
        s_subtitle = mk_style('Subtitle2', fontSize=11, textColor=colors.HexColor('#c0c0d0'), alignment=TA_CENTER, spaceAfter=2)
        s_section  = mk_style('Section2',  fontSize=13, textColor=C_WHITE,  font_name_val=font_bold, alignment=TA_LEFT)
        s_normal   = mk_style('Normal3',   fontSize=9,  textColor=C_TEXT)
        s_bold     = mk_style('Bold2',     fontSize=9,  textColor=C_TEXT,   font_name_val=font_bold)
        s_small    = mk_style('Small2',    fontSize=8,  textColor=C_TEXT)
        s_footer   = mk_style('Footer2',   fontSize=8,  textColor=colors.HexColor('#5a5a70'), alignment=TA_CENTER)

        doc = SimpleDocTemplate(filename, pagesize=A4, margin=1.5*cm)
        W = A4[0] - 3*cm
        elements = []

        # ── Шапка ────────────────────────────────────────────────────────────
        title_txt = fix_emojis(stats_data.get('title', 'Статистика чата'))
        period_txt = stats_data.get('period', '')
        date_str = f"{period_txt}  •  {stats_data.get('start_date', '')} – {stats_data.get('end_date', '')}"
        ts_str = f"Сгенерировано: {get_moscow_time().strftime('%d.%m.%Y %H:%M')} МСК"

        hdr_tbl = Table([
            [Paragraph(title_txt, s_title)],
            [Paragraph(date_str,  s_subtitle)],
            [Paragraph(ts_str,    s_subtitle)],
        ], colWidths=[W])
        hdr_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_HEADER),
            ('FONTNAME',   (0, 0), (-1, -1), font_normal),
            ('TOPPADDING',    (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(hdr_tbl)
        elements.append(Spacer(1, 0.4*cm))

        # ── 1. Общая статистика ───────────────────────────────────────────────
        if stats_data.get('general'):
            title = fix_emojis('📊  ОБЩАЯ СТАТИСТИКА')
            elements.append(Table(
                [[Paragraph(f'  {title}', s_section)]],
                colWidths=[W],
                style=[('BACKGROUND', (0,0), (-1,-1), C_ACCENT)]
            ))
            rows = [
                [Paragraph(fix_emojis(str(k)), s_normal), Paragraph(str(v), s_bold)]
                for k, v in stats_data['general'].items()
            ]
            t = Table(rows, colWidths=[W * 0.65, W * 0.35])
            t.setStyle(TableStyle([
                ('GRID',     (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME', (0,0), (-1,-1), font_normal),
                ('ALIGN',    (1,0), (1,-1),  'RIGHT'),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.4*cm))

        # ── 2. Топ активистов ─────────────────────────────────────────────────
        if stats_data.get('top_messages'):
            title = fix_emojis('🏆  ТОП-10 АКТИВИСТОВ')
            elements.append(Table(
                [[Paragraph(f'  {title}', s_section)]],
                colWidths=[W],
                style=[('BACKGROUND', (0,0), (-1,-1), C_ACCENT2)]
            ))
            cols   = ['№', 'Пользователь', 'Сообщ.', 'КОРП', 'КПРП', 'КОПЯП', 'КОПЮП', 'КУПП', 'Медиа', fix_emojis('💎 Добыто')]
            widths = [0.8*cm, 3.4*cm, 1.8*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.4*cm, 2.5*cm]

            tbl_data = [[
                Paragraph(c, mk_style(f'th_{i}', font_name_val=font_bold, fontSize=8, textColor=C_WHITE, alignment=TA_CENTER))
                for i, c in enumerate(cols)
            ]]
            for i, u in enumerate(stats_data['top_messages']):
                tbl_data.append([
                    Paragraph(str(i + 1),                        s_small),
                    Paragraph(str(u.get('Пользователь', '—')),   s_small),
                    Paragraph(_fmt_pdf(u.get('Сообщений', 0), 0), s_small),   # Decimal fmt
                    Paragraph(_fmt_pdf(u.get('КОРП', 0), 0),     s_small),
                    Paragraph(_fmt_pdf(u.get('КПРП', 0), 0),     s_small),
                    Paragraph(_fmt_pdf(u.get('КОПЯП', 0), 0),    s_small),
                    Paragraph(_fmt_pdf(u.get('КОПЮП', 0), 0),    s_small),
                    Paragraph(_fmt_pdf(u.get('КУПП', 0), 0),     s_small),
                    Paragraph(_fmt_pdf(u.get('МедиаП', 0), 0),   s_small),
                    Paragraph(_fmt_pdf(u.get('💎 Добыто', 0), 2), s_small),   # 2 знака
                ])
            t = Table(tbl_data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), C_ACCENT2),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME',   (0,0), (-1,-1), font_normal),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.4*cm))

        # ── 3. Топ по заработку ───────────────────────────────────────────────
        if stats_data.get('top_earners'):
            title = fix_emojis('💎  ТОП-10 ПО ЗАРАБОТКУ')
            elements.append(Table(
                [[Paragraph(f'  {title}', s_section)]],
                colWidths=[W],
                style=[('BACKGROUND', (0,0), (-1,-1), C_GOLD)]
            ))
            earn_keys = ['Место', 'Пользователь', fix_emojis('💎 Добыто Пульсов'), 'Сообщений']
            tbl_data = [[
                Paragraph(fix_emojis(c), mk_style(f'the_{i}', font_name_val=font_bold, fontSize=8, alignment=TA_CENTER))
                for i, c in enumerate(earn_keys)
            ]]
            for u in stats_data['top_earners']:
                tbl_data.append([
                    Paragraph(str(u.get('Место', '—')),                            s_small),
                    Paragraph(str(u.get('Пользователь', '—')),                     s_small),
                    Paragraph(_fmt_pdf(u.get('💎 Добыто Пульсов', 0), 2),          s_small),  # Decimal
                    Paragraph(_fmt_pdf(u.get('Сообщений', 0), 0),                  s_small),
                ])
            t = Table(tbl_data, colWidths=[1.5*cm, 6*cm, 6*cm, 4.4*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), C_GOLD),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME',   (0,0), (-1,-1), font_normal),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.4*cm))

        # ── 4. Периоды ────────────────────────────────────────────────────────
        if stats_data.get('daily_stats'):
            title = fix_emojis('📅  СТАТИСТИКА ПО ПЕРИОДАМ')
            elements.append(Table(
                [[Paragraph(f'  {title}', s_section)]],
                colWidths=[W],
                style=[('BACKGROUND', (0,0), (-1,-1), C_HEADER)]
            ))
            d_cols = ['Дата', 'Сообщ.', 'Актив.', 'Вступ.', 'Вышло', fix_emojis('💎 Пульсов'), 'Вовлеч.']
            tbl_data = [[
                Paragraph(fix_emojis(c), mk_style(f'thd_{i}', font_name_val=font_bold, fontSize=8, textColor=C_WHITE, alignment=TA_CENTER))
                for i, c in enumerate(d_cols)
            ]]
            for d in stats_data['daily_stats']:
                eng = to_decimal(d.get('engagement', 0))           # Decimal, не float
                tbl_data.append([
                    Paragraph(str(d.get('date', '—')),              s_small),
                    Paragraph(_fmt_pdf(d.get('messages', 0), 0),    s_small),
                    Paragraph(_fmt_pdf(d.get('active_users', 0), 0), s_small),
                    Paragraph(_fmt_pdf(d.get('joined', 0), 0),      s_small),
                    Paragraph(_fmt_pdf(d.get('left_users', 0), 0),  s_small),
                    Paragraph(_fmt_pdf(d.get('pulses', 0), 2),      s_small),   # 2 знака
                    Paragraph(f"{float(round_decimal(eng, 1)):.1f}%", s_small), # Decimal round
                ])
            t = Table(tbl_data, colWidths=[2.6*cm, 2.2*cm, 2.0*cm, 1.8*cm, 1.8*cm, 2.4*cm, 3.1*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), C_HEADER),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME',   (0,0), (-1,-1), font_normal),
            ]))
            elements.append(t)

        # Футер
        elements.append(Spacer(1, 1*cm))
        elements.append(HRFlowable(width=W, thickness=0.5, color=colors.grey))
        elements.append(Paragraph(
            fix_emojis(f"💎 ПУЛЬС — Аналитика чата  •  {get_moscow_time().strftime('%d.%m.%Y %H:%M:%S')} МСК"),
            s_footer
        ))

        doc.build(elements)
        return filename

    except Exception as e:
        print(f"Error creating PDF: {e}")
        traceback.print_exc()
        return None
