"""Resolve portable folder preferences and check the selected destination."""
from pathlib import Path
import tempfile


def resolve_folder(app,setting=None):
    app=Path(app).resolve()
    if not setting:return app/'Результаты'
    if not isinstance(setting,dict) or not isinstance(setting.get('path'),str):
        raise ValueError('Не удалось прочитать выбранную папку отчётов в Data/settings.json.')
    path=Path(setting['path'])
    if setting.get('relative') is True:
        result=(app/path).resolve()
        if path.is_absolute() or not result.is_relative_to(app):raise ValueError('Неверный путь папки отчётов в Data/settings.json.')
        return result
    if not path.is_absolute():raise ValueError('Нужен полный путь к папке отчётов.')
    return path.resolve()


def folder_setting(app,path):
    app=Path(app).resolve();path=Path(path).resolve()
    if path.is_relative_to(app):return {'path':path.relative_to(app).as_posix(),'relative':True}
    return {'path':str(path),'relative':False}


def check_folder(path,create=False):
    path=Path(path)
    try:
        if create:path.mkdir(parents=True,exist_ok=True)
        if not path.is_dir():raise OSError('Folder unavailable')
        # A write probe catches unavailable disks and read-only destinations before export.
        with tempfile.NamedTemporaryFile(prefix='.tochki-',dir=path) as probe:probe.write(b'1');probe.flush()
    except OSError as error:
        raise ValueError(f'Не удалось сохранить файлы в «{path}». Проверьте доступ к диску или выберите другую папку отчётов.') from error
    return path.resolve()
