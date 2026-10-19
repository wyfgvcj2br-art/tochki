"""Test the packaged app, not the build-time Python environment (Windows CI)."""
import argparse,io,json,os,re,subprocess,time,urllib.request,uuid,zipfile
from pathlib import Path
import openpyxl
parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);args=parser.parse_args();folder=args.folder.resolve();output=folder/'Smoke reports';settingsfile=folder/'Data/settings.json';settingsfile.parent.mkdir(exist_ok=True)
assert not settingsfile.exists(),'Smoke test requires a fresh build folder.'
settingsfile.write_text(json.dumps({'outputFolder':{'path':'Smoke reports','relative':True}}),encoding='utf-8')
proc=subprocess.Popen([str(folder/'Точки.exe')],cwd=folder)
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
try:
 statefile=folder/'Data/desktop-state.json'
 for _ in range(90):
  try:
   state=json.loads(statefile.read_text())
   if state.get('pid')==proc.pid and state.get('ready'):break
  except (OSError,ValueError):pass
  if proc.poll() is not None:raise RuntimeError('EXE завершился при запуске')
  time.sleep(1)
 else:raise RuntimeError('Окно встроенного WebView2 не загрузилось за 90 секунд')
 state=json.loads(statefile.read_text());assert Path(state['app']).resolve()==folder;assert Path(state['runtime']).is_relative_to(folder/'WebView2');assert state['mode']=='portable';url=state['url']
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
 assert not list((folder/'Результаты').iterdir())
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
 subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);proc.wait(timeout=15)
 proc=subprocess.Popen([str(folder/'Точки.exe')],cwd=folder)
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
 print('Packaged portable smoke test passed, including saved-name restart and re-upload.')
finally:
 subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
