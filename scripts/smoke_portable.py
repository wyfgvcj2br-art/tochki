"""Test the packaged app, not the build-time Python environment (Windows CI)."""
import argparse,io,json,os,re,subprocess,time,urllib.request,uuid,zipfile
from pathlib import Path
import openpyxl
parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);args=parser.parse_args();folder=args.folder.resolve();proc=subprocess.Popen([str(folder/'Точки.exe')],cwd=folder)
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
 assert (folder/'Результаты'/g['run']/'Отчёт.xlsx').is_file()
 with urllib.request.urlopen(url+g['archive']) as r:assert zipfile.ZipFile(io.BytesIO(r.read())).testzip() is None
 # Collector exports have a different grain from daily store totals.
 detail_files={'stores.xlsx':upload_bytes([['Наименование ТТ','Дата','Заказы в статусе Успешно завершен','Общее кол-во заказов, просроченных по сборке'],['9001_Демо','2026-01-05',100,5],['9001_Демо','2026-01-06',100,6]]),'collectors.xlsx':bi_export([['Наименование ТТ','date_collected','Номер сборщика','Сборщик','Заказы в статусе Успешно завершен','Общее кол-во заказов, просроченных по сборке'],['9001_Демо','2026-01-06','1','Демо Сборщик',40,6],['9001_Демо','2026-01-06','2','N/A',60,0]])}
 boundary=uuid.uuid4().hex;body=b''
 for filename,blob in detail_files.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n\r\n'.encode()+blob+b'\r\n'
 body+=f'--{boundary}--\r\n'.encode()
 a=call('/api/analyze',body,'multipart/form-data; boundary='+boundary);assert not a['errors'] and a['collectorCount']==2 and a['dailyCount']==2,a
 payload=json.dumps({'id':a['id'],'options':{'codes':['9001'],'mode':'details','excludeUnknown':True}}).encode()
 preview=call('/api/preview',payload);assert preview['badDays']==1 and preview['collectorCount']==2 and preview['unknownCollectors']==1
 assert preview['groups'][0]['days'][0]['date']=='2026-01-06'
 g=call('/api/generate',payload);assert g['audit']['mode']=='details' and g['audit']['orders']==100 and g['audit']['late']==6 and len(g['images'])==1
 with urllib.request.urlopen(url+g['archive']) as r:assert zipfile.ZipFile(io.BytesIO(r.read())).testzip() is None
 print('Packaged portable smoke test passed.')
finally:
 subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
