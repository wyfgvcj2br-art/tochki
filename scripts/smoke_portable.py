"""Test the packaged app, not the build-time Python environment (Windows CI)."""
import argparse,ctypes,io,json,os,re,subprocess,sys,time,urllib.request,uuid,zipfile
from pathlib import Path
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from app_paths import paths
from settings_store import save_settings
parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
parser.add_argument('--installed',action='store_true');parser.add_argument('--standard-user',action='store_true');parser.add_argument('--shortcut',type=Path);parser.add_argument('--reuse',action='store_true')
args=parser.parse_args();folder=args.folder.resolve()
if args.standard_user:
 from windows_test_environment import restore_user_environment
 restore_user_environment()
locations=paths(app=folder,mode='installed' if args.installed else 'portable')
locations.ensure()
if args.standard_user:assert not ctypes.windll.shell32.IsUserAnAdmin(),'Expected a non-administrator account'
output=locations.reports.parent/'Проверка отчётов с пробелами' if args.installed else folder/'Smoke reports'
settingsfile=locations.data/'settings.json';settingsfile.parent.mkdir(exist_ok=True)
if args.installed and not args.reuse:
 from portable_migration import preview_import,import_data
 source=locations.data.parent/'Старая Portable с пробелами';(source/'Data').mkdir(parents=True,exist_ok=True)
 (source/'Data/settings.json').write_text(json.dumps({'theme':'light','options':{'codes':['9001'],'good':6,'bad':10,'mode':'combined','excludeUnknown':True,'journal':True,'outline':False},'outputFolder':{'path':str(output),'relative':False}}),encoding='utf-8')
 for name in ('collector-names.json','collector-names.json.bak'):(source/'Data'/name).write_text('{"version":1,"entries":{}}',encoding='utf-8')
 before={p.name:p.read_bytes() for p in (source/'Data').iterdir()}
 imported=import_data(preview_import(source,locations.data),locations.data)
 assert len(imported['files'])==3
 assert before=={p.name:p.read_bytes() for p in (source/'Data').iterdir()},'Portable source was modified'
 assert (locations.data/'collector-names.json.bak').is_file()
 assert json.loads(settingsfile.read_text())['theme']=='light'

if not args.installed:
 assert not settingsfile.exists(),'Smoke test requires a fresh build folder.'
 save_settings(settingsfile,{'outputFolder':{'path':'Smoke reports','relative':True}})
elif args.reuse:
 assert settingsfile.is_file() and json.loads(settingsfile.read_text())['theme']=='light','Settings did not survive upgrade/reinstall'
 assert (locations.data/'survival.txt').read_text(encoding='utf-8')=='сохранить'
 assert (output/'survival.txt').read_text(encoding='utf-8')=='сохранить'

launch_env=os.environ.copy()
launch_env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')+os.pathsep+os.environ['SystemRoot']
launch_env.pop('PYTHONHOME',None);launch_env.pop('PYTHONPATH',None)
proc=subprocess.Popen([str(folder/'Точки.exe')],cwd=Path(os.environ['SystemRoot']),env=launch_env)
def upload_bytes(rows):
 w=openpyxl.Workbook()
 for row in rows:w.active.append(row)
 blob=io.BytesIO();w.save(blob);return blob.getvalue()
def bi_export(rows):
 blob=upload_bytes(rows);output=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(blob)) as source,zipfile.ZipFile(output,'w') as target:
  for name in source.namelist():
   value=source.read(name)
   if name=='xl/worksheets/sheet1.xml':value=re.sub(rb'<dimension\b[^>]*/>',b'<dimension ref="A1"/>',value)
   target.writestr(name,value)
 return output.getvalue()

def webview_pids():
 command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
 raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],text=True,encoding='utf-8',errors='replace').strip()
 if not raw:return []
 records=json.loads(raw);records=records if isinstance(records,list) else [records]
 return [int(p['ProcessId']) for p in records if str(folder).casefold() in (p.get('CommandLine') or '').casefold()]
def process_alive(pid):
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_bool,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p
 handle=kernel.OpenProcess(0x100000,False,pid)
 if not handle:return False
 try:
  kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
  return kernel.WaitForSingleObject(handle,0)==258
 finally:
  kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
def close_app(process,state):
 children=webview_pids()
 assert children,'No WebView2 child processes found for cleanup verification'
 hwnd=state.get('hwnd');assert hwnd,'No native window handle was recorded'
 user=ctypes.WinDLL('user32');user.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
 assert user.PostMessageW(hwnd,0x10,0,0)
 process.wait(timeout=25)
 for _ in range(30):
  if not any(process_alive(pid) for pid in children):break
  time.sleep(.5)
 assert not any(process_alive(pid) for pid in children),'WebView2 children survived normal window close'

try:
 statefile=(locations.logs if args.installed else locations.data)/'desktop-state.json'
 for _ in range(90):
  try:
   state=json.loads(statefile.read_text())
   if state.get('pid')==proc.pid and state.get('ready'):break
  except (OSError,ValueError):pass
  if proc.poll() is not None:raise RuntimeError('EXE завершился при запуске')
  time.sleep(1)
 else:raise RuntimeError('Окно встроенного WebView2 не загрузилось за 90 секунд')
 state=json.loads(statefile.read_text());assert Path(state['app']).resolve()==folder;assert Path(state['runtime']).is_relative_to(folder/'WebView2');assert state['mode']==('installed' if args.installed else 'portable');url=state['url']
 assert Path(state['data'])==locations.data and Path(state['webview'])==locations.webview
 assert state.get('smartScreen') is False,'Local WebView SmartScreen setting was not applied'
 boundary=uuid.uuid4().hex;body=b''
 files={'daily.xlsx':upload_bytes([['Наименование ТТ','Дата','Заказы в статусе Успешно завершен','Общее кол-во заказов, просроченных по сборке','Помощник'],['9001_Демо','2026-01-05',100,5,'Демо']]),'appeals.xlsx':bi_export([['Примененные фильтры: контрольный экспорт'],[],['Сборщик','ТТ','абс','Дни'],['Тестовый Сотрудник(123)','9001_Демо',1,'2026-01-05'],['Ранее(456)','9001_Демо',2,'2025-07-17'],['Позже(789)','9001_Демо',3,'2026-01-06']])}
 for filename,blob in files.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n\r\n'.encode()+blob+b'\r\n'
 body+=f'--{boundary}--\r\n'.encode()
 def call(path,body,content_type='application/json'):
  req=urllib.request.Request(url+path,data=body,headers={'Content-Type':content_type,'X-Local-App':'tt-reports','Origin':url})
  with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
 a=call('/api/analyze',body,'multipart/form-data; boundary='+boundary);assert not a['errors'],a;assert a['appealCount']==3,a
 preview=call('/api/preview',json.dumps({'id':a['id'],'options':{'codes':['9001'],'mode':'combined'}}).encode());assert preview['dates']==['2026-01-05'] and preview['appeals']==1 and preview['outsidePeriodRecords']==2 and preview['outsidePeriodAppeals']==5 and preview['warnings']
 g=call('/api/generate',json.dumps({'id':a['id'],'options':{'codes':['9001'],'mode':'combined','journal':True,'excludeUnknown':True}}).encode());assert g['audit']['orders']==100 and g['audit']['late']==5 and g['audit']['appeals']==1
 assert g['audit']['outsidePeriodRecords']==2 and g['audit']['outsidePeriodAppeals']==5
 assert (output/g['run']/'Отчёт.xlsx').is_file()
 assert Path(g['folder']).parent==output
 if args.installed:
  assert not (folder/'Data').exists() and not (folder/'Результаты').exists()
 else:assert not list((folder/'Результаты').iterdir())
 with urllib.request.urlopen(url+g['archive']) as r:assert zipfile.ZipFile(io.BytesIO(r.read())).testzip() is None
 # Collector exports have a different grain from daily store totals.
 detail_files={'stores.xlsx':upload_bytes([['Наименование ТТ','Дата','Заказы в статусе Успешно завершен','Общее кол-во заказов, просроченных по сборке'],['9001_Демо','2026-01-05',100,5],['9001_Демо','2026-01-06',100,6]]),'collectors.xlsx':bi_export([['Наименование ТТ','date_collected','Номер сборщика','Сборщик','Заказы в статусе Успешно завершен','Общее кол-во заказов, просроченных по сборке'],['9001_Демо','2026-01-06','1','Демо Сборщик',40,5],['9001_Демо','2026-01-06','2','N/A',60,0]])}
 boundary=uuid.uuid4().hex;body=b''
 for filename,blob in detail_files.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n\r\n'.encode()+blob+b'\r\n'
 body+=f'--{boundary}--\r\n'.encode()
 a=call('/api/analyze',body,'multipart/form-data; boundary='+boundary);assert not a['errors'] and a['collectorCount']==2 and a['dailyCount']==2,a
 payload=json.dumps({'id':a['id'],'options':{'codes':['9001'],'mode':'details','excludeUnknown':True}}).encode()
 preview=call('/api/preview',payload);assert preview['badDays']==1 and preview['collectorCount']==2 and preview['unknownCollectors']==1 and preview['mismatchCount']==1 and preview['measureSource']=='collectors'
 assert preview['groups'][0]['days'][0]['date']=='2026-01-06'
 g=call('/api/generate',payload);assert g['audit']['mode']=='details' and g['audit']['orders']==100 and g['audit']['late']==5 and g['audit']['storeLate']==6 and g['audit']['mismatchCount']==1 and len(g['images'])==1
 with urllib.request.urlopen(url+g['archive']) as r:assert zipfile.ZipFile(io.BytesIO(r.read())).testzip() is None
 # Confirmed names must persist across process restart and new uploads.
 view=call('/api/collector-names',b'{}');assert not view['entries']
 assert [r['id'] for r in a['nameDirectory']['pending']]==['2']
 view=call('/api/collector-names/save',json.dumps({'id':a['id'],'revision':view['revision'],'entries':[{'id':'2','name':'Демо Сохранённый Сборщик'}]}).encode())
 assert not view['pending'] and len(view['entries'])==1
 preview=call('/api/preview',payload);assert preview['unknownCollectors']==0 and preview['orders']==100 and preview['late']==5
 g=call('/api/generate',payload);assert g['audit']['nameBindingsUsed']==[{'id':'2','name':'Демо Сохранённый Сборщик'}]
 w=openpyxl.load_workbook(output/g['run']/'Отчёт.xlsx');assert any(r[0]=='Демо Сохранённый Сборщик' for r in w.active.values);w.close()
 close_app(proc,state)
 proc=subprocess.Popen([str(folder/'Точки.exe')],cwd=Path(os.environ['SystemRoot']),env=launch_env)
 for _ in range(90):
  try:
   state=json.loads(statefile.read_text())
   if state.get('pid')==proc.pid and state.get('ready'):break
  except (OSError,ValueError):pass
  if proc.poll() is not None:raise RuntimeError('EXE завершился при повторном запуске')
  time.sleep(1)
 else:raise RuntimeError('Повторный запуск EXE: timeout')
 url=state['url']
 with urllib.request.urlopen(url+'/api/output-folder') as r:assert json.load(r)['path']==str(output)
 view=call('/api/collector-names',b'{}');assert view['entries'][0]['name']=='Демо Сохранённый Сборщик'
 a=call('/api/analyze',body,'multipart/form-data; boundary='+boundary);assert not a['nameDirectory']['pending']
 preview=call('/api/preview',json.dumps({'id':a['id'],'options':{'codes':['9001'],'mode':'details'}}).encode());assert preview['unknownCollectors']==0 and preview['orders']==100 and preview['late']==5
 call('/api/collector-names/remove',json.dumps({'revision':view['revision'],'collectorId':'2'}).encode())
 assert not call('/api/collector-names',b'{}')['entries']
 if args.installed:
  (locations.data/'survival.txt').write_text('сохранить',encoding='utf-8')
  (output/'survival.txt').write_text('сохранить',encoding='utf-8')
  assert json.loads(settingsfile.read_text())['theme']=='light'
 close_app(proc,state)
 if args.shortcut:
  statefile.unlink(missing_ok=True)
  os.startfile(args.shortcut)
  for _ in range(90):
   try:
    shortcut_state=json.loads(statefile.read_text())
    if shortcut_state.get('ready'):break
   except (OSError,ValueError):pass
   time.sleep(1)
  else:raise RuntimeError('Start menu shortcut did not start the app')
  assert Path(shortcut_state['app']).resolve()==folder
  class StartedProcess:
   def wait(self,timeout):
    for _ in range(int(timeout*2)):
     if not process_alive(shortcut_state['pid']):return
     time.sleep(.5)
    raise RuntimeError('Shortcut-launched process did not exit')
  close_app(StartedProcess(),shortcut_state)
 print('Packaged smoke test passed: reports, saved-name restart, settings, normal close, WebView2 cleanup; installed='+str(args.installed))
except Exception:
 if (locations.logs/'Ошибка.txt').is_file():
  print((locations.logs/'Ошибка.txt').read_text(encoding='utf-8'))
 raise
finally:
 if proc.poll() is None:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
