"""Explicit, reviewed and transactional import; never modifies the portable source."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import threading
import uuid
from pathlib import Path
from collector_names import bindable,collector_id,valid_name,NameDirectory
from output_folders import resolve_folder
from settings_store import atomic_write,validate_settings

FILES=('settings.json','collector-names.json','collector-names.json.bak')
_LOCK=threading.RLock()
MAX_FILE=4*1024*1024

def digest(blob):
    return hashlib.sha256(blob).hexdigest() if blob is not None else None

def read_file(path):
    if path.is_symlink():
        raise ValueError(f'Символические ссылки не импортируются: {path.name}.')
    if not path.exists():return None
    if not path.is_file() or path.stat().st_size>MAX_FILE:
        raise ValueError(f'Некорректный или слишком большой файл: {path.name}.')
    return path.read_bytes()

def validate_names(blob):
    value=json.loads(blob.decode('utf-8-sig'))
    if not isinstance(value,dict) or value.get('version')!=1 or not isinstance(value.get('entries'),dict):
        raise ValueError('Неизвестный формат справочника.')
    for key,entry in value['entries'].items():
        if (not bindable(key) or collector_id(key)!=key or not isinstance(entry,dict)
                or valid_name(entry.get('name'))!=entry['name']):
            raise ValueError('Некорректная привязка ФИО в справочнике.')
        if 'tts' in entry and (not isinstance(entry['tts'],list) or any(not isinstance(tt,str) for tt in entry['tts'])):
            raise ValueError('Некорректный список ТТ в справочнике.')
        if 'updatedAt' in entry and not isinstance(entry['updatedAt'],str):
            raise ValueError('Некорректная дата в справочнике.')
    return value

def migration_status(data):
    marker=Path(data)/'migration.json'
    try:
        value=json.loads(marker.read_text(encoding='utf-8'))
        return {'pending':value.get('status') not in ('imported','skipped')}
    except (OSError,ValueError,AttributeError):
        return {'pending':True}

def skip_import(data):
    atomic_write(Path(data)/'migration.json',json.dumps(
        {'version':1,'status':'skipped','at':dt.datetime.now().isoformat()}).encode())
    return {'ok':True}

def preview_import(portable,data):
    source=Path(portable).resolve()
    target=Path(data).resolve()
    root=source/'Data'
    if root.is_symlink() or not root.is_dir() or root.resolve()==target:
        raise ValueError('Выберите старую папку Portable с отдельным каталогом Data.')
    blobs={};targets={};items=[]
    for name in FILES:
        file=root/name
        if not file.resolve().is_relative_to(root.resolve()):
            raise ValueError('Файл выходит за пределы выбранной папки Data.')
        blob=read_file(file)
        if blob is None:continue
        try:
            if name=='settings.json':
                settings=validate_settings(json.loads(blob.decode('utf-8-sig')))
                if settings.get('outputFolder'):
                    destination=resolve_folder(source,settings['outputFolder'])
                    settings['outputFolder']={'path':str(destination),'relative':False}
                normalized=json.dumps(settings,ensure_ascii=False,indent=2).encode('utf-8')
            else:
                validate_names(blob)
                normalized=blob.removeprefix(b'\xef\xbb\xbf')
        except (ValueError,KeyError,TypeError,UnicodeError) as error:
            raise ValueError(f'Импорт остановлен: неверный файл {name}. {error}') from error
        current=read_file(target/name)
        blobs[name]={'source':blob,'output':normalized}
        targets[name]=current
        items.append({'name':name,'replace':current is not None,'bytes':len(blob)})
    if not blobs:
        raise ValueError('В Data не найдены настройки или справочник для импорта.')
    review={'source':str(source),'files':items,
            'sourceHashes':{name:digest(item['source']) for name,item in blobs.items()},
            'targetHashes':{name:digest(blob) for name,blob in targets.items()}}
    return review

def import_data(review,data,confirm_replace=False):
    target=Path(data).resolve()
    with _LOCK,NameDirectory(target).locked():
        fresh=preview_import(review['source'],target)
        if fresh!=review:
            raise ValueError('Файлы изменились после проверки. Выберите папку и проверьте импорт ещё раз.')
        if any(item['replace'] for item in fresh['files']) and not confirm_replace:
            raise ValueError('Замена существующих данных требует подтверждения.')
        snapshot={item['name']:read_file(target/item['name']) for item in fresh['files']}
        marker=target/'migration.json'
        previous_marker=marker.read_bytes() if marker.exists() else None
        backup=target/'Backups'/('portable-import-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
        if any(blob is not None for blob in snapshot.values()):
            backup.mkdir(parents=True,exist_ok=False)
            for name,blob in snapshot.items():
                if blob is not None:atomic_write(backup/name,blob)
        written=[]
        try:
            for item in fresh['files']:
                name=item['name']
                blob=read_file(Path(fresh['source'])/'Data'/name)
                if digest(blob)!=fresh['sourceHashes'][name]:
                    raise ValueError('Исходный файл изменился во время импорта.')
                if name=='settings.json':
                    settings=validate_settings(json.loads(blob.decode('utf-8-sig')))
                    if settings.get('outputFolder'):
                        settings['outputFolder']={'path':str(resolve_folder(fresh['source'],settings['outputFolder'])),'relative':False}
                    blob=json.dumps(settings,ensure_ascii=False,indent=2).encode('utf-8')
                else:
                    validate_names(blob)
                    blob=blob.removeprefix(b'\xef\xbb\xbf')
                if digest(read_file(target/name))!=fresh['targetHashes'][name]:
                    raise ValueError('Пользовательские данные изменились во время импорта.')
                atomic_write(target/name,blob)
                written.append(name)
            atomic_write(marker,json.dumps({'version':1,'status':'imported',
                'at':dt.datetime.now().isoformat(),'files':written,
                'backup':str(backup) if backup.exists() else None},ensure_ascii=False,indent=2).encode('utf-8'))
        except Exception:
            for name in reversed(written):
                if snapshot[name] is None:(target/name).unlink(missing_ok=True)
                else:atomic_write(target/name,snapshot[name])
            if previous_marker is None:marker.unlink(missing_ok=True)
            else:atomic_write(marker,previous_marker)
            raise
        return {'ok':True,'files':written,'backup':str(backup) if backup.exists() else None}
