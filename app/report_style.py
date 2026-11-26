"""Shared offline PNG layout. The report calculations live in engine/details."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw

BRAND = '#2DBE64'
DARK = '#176B3A'
TEXT = '#203D2C'
MUTED = '#63786B'
PALE = '#EDF8F0'
LINE = '#D9EADD'
WIDTH = 1500
MARGIN = 32


@lru_cache(maxsize=1)
def monogram():
    # ui is already bundled by build_portable.py; no network or SVG runtime needed.
    with Image.open(Path(__file__).with_name('ui') / 'vv-monogram.png') as source:
        return source.convert('RGBA').resize((106, 60), Image.Resampling.LANCZOS)


def wrap(draw, value, face, width):
    """Wrap complete text, including long unbroken store names, without ellipses."""
    result = []
    for paragraph in str(value).split('\n'):
        line = ''
        for word in paragraph.split(' '):
            candidate = (line + ' ' + word) if line else word
            if draw.textlength(candidate, font=face) <= width:
                line = candidate
                continue
            if line:
                result.append(line)
            line = ''
            for char in word:
                if line and draw.textlength(line + char, font=face) > width:
                    result.append(line)
                    line = ''
                line += char
        result.append(line)
    return result


def text_block(draw, lines, face, x, center_y, fill, align='left'):
    step = face.size + 7
    top = center_y - (len(lines) - 1) * step / 2
    for i, line in enumerate(lines):
        draw.text((x, top + i * step), line, font=face, fill=fill,
                  anchor='lm' if align == 'left' else 'mm')


def report_picture(title, dates, path, labels, rows, edges, font,
                   report_name, subtitle='', rate_column=None, rate_color=None):
    """Render supplied display rows without interpreting or changing their values."""
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    title_face = font(36, True)
    title_lines = wrap(measure, title, title_face, WIDTH - 2 * MARGIN - 16)
    title_height = len(title_lines) * 43
    table_y = 120 + title_height + (104 if subtitle else 74)
    header_height = 76

    # Measure every column first so no names, labels or large numbers get clipped.
    prepared = []
    for values, ratio, kind in rows:
        cells = []
        for col, value in enumerate(values):
            bold = kind in ('total', 'day') or col == rate_column
            face = font(22, bold)
            indent = 20 if col == 0 and kind in ('person', 'appeal') else 0
            available = edges[col + 1] - edges[col] - 40 - indent
            lines = wrap(measure, value, face, available)
            cells.append((lines, face, indent))
        height = max(60, max(len(lines) * (face.size + 7) + 24
                             for lines, face, _ in cells))
        prepared.append((cells, ratio, kind, height))
    header_face = font(20, True)
    header_cells = [wrap(measure, label, header_face, edges[i + 1] - edges[i] - 32)
                    for i, label in enumerate(labels)]
    header_height = max(header_height, max(len(lines) * 27 + 24 for lines in header_cells))
    height = table_y + header_height + sum(row[3] for row in prepared) + 32
    im = Image.new('RGB', (WIDTH, height), 'white')
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, WIDTH, 7), fill=BRAND)
    logo = monogram()
    im.paste(logo, (40, 34), logo)
    draw.text((172, 64), 'ВкусВилл', font=font(26, True), fill=DARK, anchor='lm')
    draw.text((WIDTH - 40, 64), report_name, font=font(21), fill=MUTED, anchor='rm')
    text_block(draw, title_lines, title_face, 40, 120 + title_height / 2, TEXT)
    period = f'{dt.date.fromisoformat(dates[0]):%d.%m.%Y} — {dt.date.fromisoformat(dates[-1]):%d.%m.%Y}'
    draw.text((40, 120 + title_height + 28), period, font=font(23), fill=MUTED, anchor='lm')
    if subtitle:
        draw.text((40, 120 + title_height + 64), subtitle, font=font(20), fill=MUTED, anchor='lm')

    draw.rounded_rectangle((MARGIN, table_y, WIDTH - MARGIN, table_y + header_height + 16),
                           radius=16, fill=DARK)
    for col, lines in enumerate(header_cells):
        x = edges[col] + 20 if col == 0 else (edges[col] + edges[col + 1]) / 2
        text_block(draw, lines, header_face, x, table_y + header_height / 2, 'white',
                   'left' if col == 0 else 'center')
    y = table_y + header_height
    for cells, ratio, kind, row_height in prepared:
        total = kind == 'total'
        fill = DARK if total else PALE if kind == 'day' else 'white'
        draw.rectangle((MARGIN, y, WIDTH - MARGIN, y + row_height), fill=fill)
        if kind == 'day':
            draw.rectangle((MARGIN, y, MARGIN + 4, y + row_height - 1), fill=BRAND)
        if rate_column is not None and kind not in ('appeal',):
            left, right = edges[rate_column], edges[rate_column + 1]
            draw.rounded_rectangle((left + 12, y + 10, right - 12, y + row_height - 10),
                                   radius=10, fill=rate_color(ratio))
        for col, (lines, face, indent) in enumerate(cells):
            ink = 'white' if total else TEXT
            if col == rate_column:
                ink = TEXT
            x = edges[col] + 20 + indent if col == 0 else (edges[col] + edges[col + 1]) / 2
            text_block(draw, lines, face, x, y + row_height / 2, ink,
                       'left' if col == 0 else 'center')
        if not total:
            draw.line((MARGIN, y + row_height - 1, WIDTH - MARGIN, y + row_height - 1), fill=LINE)
        y += row_height
    im.save(path)
