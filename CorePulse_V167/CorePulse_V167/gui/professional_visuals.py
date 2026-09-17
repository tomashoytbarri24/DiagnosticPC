"""Helpers visuales compartidos para una estética profesional y consistente."""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import color as theme_color

FONT = 'Segoe UI'
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#8295ad')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
PURPLE = '#a78bfa'
RED = '#ff5d6c'

_BADGE_STYLE = {
    CYAN: (theme_color('#0d2942'), theme_color('#1d5278'), theme_color('#9bddff')),
    '#38bdf8': (theme_color('#0d2942'), theme_color('#1d5278'), theme_color('#9bddff')),
    '#60a5fa': (theme_color('#0d2942'), theme_color('#1d5278'), theme_color('#b9ddff')),
    GREEN: (theme_color('#0d332b'), theme_color('#178967'), theme_color('#baf5dc')),
    '#10b981': (theme_color('#0d332b'), theme_color('#178967'), theme_color('#baf5dc')),
    '#22c993': (theme_color('#0d332b'), theme_color('#178967'), theme_color('#baf5dc')),
    AMBER: (theme_color('#241d0f'), theme_color('#6e5421'), theme_color('#f4b942')),
    '#f0a23a': (theme_color('#241d0f'), theme_color('#6e5421'), theme_color('#f4b942')),
    '#f2b84b': (theme_color('#241d0f'), theme_color('#6e5421'), theme_color('#f4b942')),
    PURPLE: (theme_color('#152750'), theme_color('#4a4772'), theme_color('#dac5ff')),
    '#a855f7': (theme_color('#152750'), theme_color('#4a4772'), theme_color('#dac5ff')),
    '#a064ff': (theme_color('#152750'), theme_color('#4a4772'), theme_color('#dac5ff')),
    RED: (theme_color('#2b1d26'), theme_color('#693343'), theme_color('#ffb8c0')),
    '#ef4444': (theme_color('#2b1d26'), theme_color('#693343'), theme_color('#ffb8c0')),
    '#ef5b67': (theme_color('#2b1d26'), theme_color('#693343'), theme_color('#ffb8c0')),
}
_DEFAULT_BADGE = (theme_color('#102235'), theme_color('#17314d'), TEXT_2)


def _badge_spec(item, default_accent=CYAN):
    if isinstance(item, dict):
        text = str(item.get('text') or '').strip()
        accent = item.get('accent') or default_accent
    elif isinstance(item, (list, tuple)):
        text = str(item[0] if item else '').strip()
        accent = item[1] if len(item) > 1 else default_accent
    else:
        text = str(item or '').strip()
        accent = default_accent
    return text, accent


def build_badge_row(parent, badges, *, default_accent=CYAN):
    items = list(badges or ())
    row = ctk.CTkFrame(parent, fg_color='transparent')
    for index, item in enumerate(items):
        text, accent = _badge_spec(item, default_accent=default_accent)
        if not text:
            continue
        bg, border, text_color = _BADGE_STYLE.get(accent, _DEFAULT_BADGE)
        pill = ctk.CTkFrame(row, fg_color=bg, border_width=1, border_color=border, corner_radius=999)
        pill.pack(side='left', padx=(0, 6 if index < len(items) - 1 else 0))
        ctk.CTkLabel(
            pill,
            text=text,
            font=(FONT, 8, 'bold'),
            text_color=text_color,
            anchor='center',
            justify='center',
        ).pack(padx=9, pady=4)
    return row


def build_title_block(parent, *, eyebrow, title, subtitle, accent=CYAN, badges=(), title_size=19):
    wrap = ctk.CTkFrame(parent, fg_color='transparent')
    eyebrow_label = ctk.CTkLabel(
        wrap,
        text=str(eyebrow),
        font=(FONT, 8, 'bold'),
        text_color=accent,
        anchor='w',
        justify='left',
    )
    eyebrow_label.pack(anchor='w', pady=(0, 1))
    title_label = ctk.CTkLabel(
        wrap,
        text=str(title),
        font=(FONT, title_size, 'bold'),
        text_color=TEXT,
        anchor='w',
        justify='left',
    )
    title_label.pack(anchor='w')
    subtitle_label = ctk.CTkLabel(
        wrap,
        text=str(subtitle),
        font=(FONT, 10),
        text_color=TEXT_2,
        anchor='w',
        justify='left',
        wraplength=720,
    )
    subtitle_label.pack(anchor='w', pady=(2, 0))
    badges_row = None
    if badges:
        badges_row = build_badge_row(wrap, badges, default_accent=accent)
        badges_row.pack(anchor='w', pady=(6, 0))
    return {
        'frame': wrap,
        'eyebrow': eyebrow_label,
        'title': title_label,
        'subtitle': subtitle_label,
        'badges': badges_row,
    }


def build_empty_state(
    parent,
    *,
    icon='○',
    title='Sin datos todavía',
    description='',
    accent=CYAN,
    action_text=None,
    action_command=None,
    compact=False,
):
    """Estado vacío reutilizable con una acción clara y sin ruido visual."""
    bg, border, _text_color = _BADGE_STYLE.get(accent, _DEFAULT_BADGE)
    frame = ctk.CTkFrame(
        parent,
        fg_color=theme_color('#0a1726'),
        border_width=1,
        border_color=border,
        corner_radius=12,
    )
    frame.grid_columnconfigure(1, weight=1)

    size = 42 if compact else 50
    icon_box = ctk.CTkFrame(
        frame,
        width=size,
        height=size,
        fg_color=bg,
        border_width=1,
        border_color=border,
        corner_radius=12,
    )
    icon_box.grid(row=0, column=0, rowspan=2, sticky='nw', padx=(12, 10), pady=12)
    icon_box.grid_propagate(False)
    ctk.CTkLabel(
        icon_box,
        text=str(icon),
        font=(FONT, 20 if compact else 23, 'bold'),
        text_color=accent,
    ).pack(expand=True, fill='both')

    ctk.CTkLabel(
        frame,
        text=str(title),
        font=(FONT, 11 if compact else 12, 'bold'),
        text_color=TEXT,
        anchor='w',
        justify='left',
    ).grid(row=0, column=1, sticky='ew', padx=(0, 12), pady=(12, 2))

    ctk.CTkLabel(
        frame,
        text=str(description or ''),
        font=(FONT, 8 if compact else 9),
        text_color=MUTED,
        anchor='w',
        justify='left',
        wraplength=760,
    ).grid(row=1, column=1, sticky='new', padx=(0, 12), pady=(0, 12 if not action_text else 6))

    button = None
    if action_text and callable(action_command):
        button = ctk.CTkButton(
            frame,
            text=str(action_text),
            command=action_command,
            height=28 if compact else 31,
            width=132,
            corner_radius=8,
            border_width=1,
            border_color=border,
            fg_color=bg,
            hover_color=theme_color('#15314b'),
            text_color=TEXT,
            font=(FONT, 8 if compact else 9, 'bold'),
        )
        button.grid(row=2, column=1, sticky='w', padx=(0, 12), pady=(0, 12))

    return {'frame': frame, 'button': button}
