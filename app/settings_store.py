"""Validated, atomic settings; malformed user files are never silently overwritten."""
from __future__ import annotations
import json
import math
import os
import tempfile
from pathlib import Path

def atomic_write(path, blob):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.tochki-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def validate_settings(value):
    if not isinstance(value, dict):
        raise ValueError('Настройки должны быть объектом JSON.')
    if 'theme' in value and value['theme'] not in ('dark', 'light'):
        raise ValueError('Некорректная тема настроек.')
    if 'outputFolder' in value:
        setting = value['outputFolder']
        if (not isinstance(setting, dict) or not isinstance(setting.get('path'), str)
                or not setting['path'] or '\x00' in setting['path']
                or not isinstance(setting.get('relative', False), bool)):
            raise ValueError('Некорректная папка отчётов в настройках.')
    options = value.get('options', {})
    if not isinstance(options, dict):
        raise ValueError('Некорректные параметры отчёта.')
    if 'codes' in options and (not isinstance(options['codes'], list)
            or len(options['codes']) > 1000 or any(not isinstance(c, str) or not c or len(c)>100 for c in options['codes'])):
        raise ValueError('Некорректный список ТТ.')
    for key in ('excludeUnknown', 'journal', 'outline'):
        if key in options and not isinstance(options[key], bool):
            raise ValueError('Некорректные переключатели отчёта.')
    for key in ('good', 'bad'):
        if key in options and (type(options[key]) not in (int, float)
                or not math.isfinite(options[key]) or not 0 <= options[key] <= 100):
            raise ValueError('Некорректные пороги просрока.')
    if 'good' in options and 'bad' in options and options['good'] >= options['bad']:
        raise ValueError('Зелёный порог должен быть меньше красного.')
    if 'mode' in options and options['mode'] not in ('combined', 'late', 'appeals', 'details'):
        raise ValueError('Неизвестный тип отчёта.')
    return value

def read_settings(path):
    try:
        return validate_settings(json.loads(Path(path).read_text(encoding='utf-8-sig')))
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError) as error:
        raise ValueError(f'Не удалось прочитать настройки «{path}». Файл сохранён. Восстановите резервную копию или импортируйте настройки из Portable.') from error

def save_settings(path, value):
    validate_settings(value)
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))
