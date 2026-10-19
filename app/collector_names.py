"""Portable, user-confirmed collector ID -> name directory."""
from __future__ import annotations
import contextlib,datetime as dt,hashlib,json,os,re,tempfile,threading
from pathlib import Path

_LOCK=threading.RLock()


def collector_id(value):
    text=str(value if value is not None else '').strip()
    if re.fullmatch(r'\d+(?:\.0+)?',text):return str(int(text.split('.')[0]))
    return text


def bindable(value):
    value=collector_id(value)
    return value.isdecimal() and int(value)>0


def valid_name(value):
    if not isinstance(value,str):raise ValueError('Введите ФИО текстом.')
    name=' '.join(value.split())
    if not 2<=len(name)<=160 or not any(c.isalpha() for c in name) or not all(c.isalpha() or c in " -.'’" for c in name):
        raise ValueError('Введите ФИО без числового кода: буквы, пробелы, дефис и инициалы.')
    if name.casefold().replace('ё','е') in {'неопределенный пользователь','фио не указано','неизвестно'}:raise ValueError('Введите настоящее ФИО сборщика.')
    return name


class NameDirectory:
    def __init__(self,root):
        self.root=Path(root);self.path=self.root/'collector-names.json'

    def read(self):
        try:blob=self.path.read_bytes()
        except FileNotFoundError:return {'entries':{},'revision':hashlib.sha256(b'').hexdigest()}
        try:
            value=json.loads(blob.decode('utf-8'));entries=value['entries']
            if value.get('version')!=1 or not isinstance(entries,dict):raise ValueError()
            for key,entry in entries.items():
                if not bindable(key) or collector_id(key)!=key or not isinstance(entry,dict) or valid_name(entry['name'])!=entry['name']:raise ValueError()
        except (ValueError,KeyError,TypeError,UnicodeError) as error:
            raise ValueError('Не удалось прочитать справочник Data/collector-names.json. Файл сохранён; проверьте резервную копию collector-names.json.bak.') from error
        return {'entries':entries,'revision':hashlib.sha256(blob).hexdigest()}

    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with _LOCK,open(self.root/'.collector-names.lock','a+b') as handle:
            handle.seek(0,os.SEEK_END)
            if not handle.tell():handle.write(b'0');handle.flush()
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
                try:yield
                finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX)
                try:yield
                finally:fcntl.flock(handle,fcntl.LOCK_UN)

    def atomic_write(self,path,blob):
        fd,temp=tempfile.mkstemp(prefix='.collector-names-',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):os.unlink(temp)

    def save(self,updates,revision,sightings=None,remove=None):
        if not isinstance(updates,list) or len(updates)>1000:raise ValueError('Не удалось прочитать список привязок ФИО.')
        validated={}
        for entry in updates:
            if not isinstance(entry,dict):raise ValueError('Не удалось прочитать привязку ФИО.')
            key=collector_id(entry.get('id'))
            if not bindable(key):raise ValueError('ID 0 и пустой ID не определяют одного сборщика. Нужен настоящий номер из 1С.')
            if key in validated:raise ValueError('Один ID указан несколько раз.')
            validated[key]=valid_name(entry.get('name'))
        remove=collector_id(remove) if remove is not None else None
        with self.locked():
            current=self.read()
            if not isinstance(revision,str) or revision!=current['revision']:raise ValueError('Справочник изменился в другом окне. Обновите список и повторите сохранение.')
            entries={k:dict(v) for k,v in current['entries'].items()}
            if remove is not None:
                if remove not in entries:raise ValueError('Привязка уже отсутствует. Обновите список.')
                del entries[remove]
            for key,name in validated.items():
                seen=(sightings or {}).get(key,{})
                old=entries.get(key,{})
                entries[key]={'name':name,'updatedAt':dt.datetime.now().isoformat(timespec='seconds'),
                              'tts':sorted(set(old.get('tts',[]))|set(seen.get('tts',[])))}
            blob=json.dumps({'version':1,'entries':entries},ensure_ascii=False,indent=2).encode('utf-8')
            if self.path.exists():self.atomic_write(self.path.with_suffix('.json.bak'),self.path.read_bytes())
            self.atomic_write(self.path,blob)
            return self.read()


def sightings(data):
    found={}
    for row in (data or {}).get('collectors',[]):
        key=collector_id(row.get('collectorId'))
        item=found.setdefault(key,{'id':key,'tts':set(),'dates':set(),'knownNames':set(),'missingRows':0})
        item['tts'].add(row['tt']);item['dates'].add(row['date'])
        if row.get('name'):item['knownNames'].add(row['name'])
        else:item['missingRows']+=1
    return {key:{**v,'tts':sorted(v['tts']),'dates':sorted(v['dates']),'knownNames':sorted(v['knownNames'])} for key,v in found.items()}


def directory_view(data,state):
    seen=sightings(data);pending=[]
    for key,item in sorted(seen.items()):
        if key!='0' and item['missingRows'] and key not in state['entries']:
            pending.append({**item,'bindable':bindable(key)})
    entries=[{'id':key,**value,'tts':sorted(set(value.get('tts',[]))|set(seen.get(key,{}).get('tts',[])))} for key,value in sorted(state['entries'].items())]
    return {'revision':state['revision'],'pending':pending,'entries':entries,'path':'Data/collector-names.json'}


def apply_directory(data,state):
    rows=[];used={};warnings=list(data['warnings']);conflicts=set()
    for original in data.get('collectors',[]):
        row=dict(original);key=collector_id(row.get('collectorId'));row['collectorId']=key
        entry=state['entries'].get(key)
        if entry and not row.get('name'):
            row.update(name=entry['name'],nameFromRegistry=True,originalName=original.get('name',''))
            used[key]=entry['name']
        elif entry and row.get('name') and row['name']!=entry['name']:
            conflicts.add((key,row['name'],entry['name']))
        rows.append(row)
    for key,exported,mapped in sorted(conflicts):warnings.append(f'ID {key}: в выгрузке «{exported}», в справочнике «{mapped}». Заполненное ФИО из выгрузки сохранено; проверьте привязку.')
    return {**data,'collectors':rows,'warnings':warnings,'nameBindingsUsed':[{'id':key,'name':name} for key,name in sorted(used.items())],'nameRegistryRevision':state['revision']}
