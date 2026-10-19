from __future__ import annotations
import argparse,datetime as dt,hashlib,io,json,mimetypes,os,secrets,sys,threading,time,traceback,urllib.parse,webbrowser
from email.parser import BytesParser
from email.policy import default
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from engine import analyze,generate,select,selection_inputs,DEFAULT_CODES
from collector_names import NameDirectory,directory_view,sightings,apply_directory
ASSETS=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TT_DATA_DIR',str(ASSETS)));ROOT.mkdir(parents=True,exist_ok=True)
RESULTS=Path(os.environ.get('TT_OUTPUT_DIR',str(ROOT/'Результаты')))
NAMES=NameDirectory(ROOT)
JOBS={};RUNS={};LOCK=threading.Lock();APP_ID=hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
def json_bytes(v):return json.dumps(v,ensure_ascii=False).encode('utf-8')
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def reply(self,status,data,ctype='application/json; charset=utf-8'):
        blob=json_bytes(data) if isinstance(data,(dict,list)) else data
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(blob)
    def do_GET(self):
        try:
            p=urllib.parse.urlparse(self.path).path
            if self.headers.get('Host') not in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']:return self.reply(403,{'error':'Недопустимый адрес приложения.'})
            if p=='/api/health':return self.reply(200,{'app':APP_ID})
            if p=='/api/config':return self.reply(200,{'codes':DEFAULT_CODES,'version':'1.0'})
            if p.startswith('/files/'):
                bits=p.split('/');rid=bits[2];filename=urllib.parse.unquote('/'.join(bits[3:]));folder=RUNS.get(rid)
                if not folder:return self.reply(404,{'error':'Файл не найден.'})
                file=(folder/filename).resolve()
                if not file.is_relative_to(folder.resolve()) or not file.is_file():return self.reply(404,{'error':'Файл не найден.'})
                blob=file.read_bytes();return self.reply(200,blob,mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
            if p=='/':p='/index.html'
            file=(ASSETS/'ui'/p.lstrip('/')).resolve()
            if not file.is_relative_to((ASSETS/'ui').resolve()) or not file.is_file():return self.reply(404,{'error':'Страница не найдена.'})
            self.reply(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        except Exception:self.reply(500,{'error':'Не удалось прочитать файл.'})
    def do_POST(self):
        try:
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected or self.headers.get('X-Local-App')!='tt-reports':return self.reply(403,{'error':'Запрос разрешён только из приложения.'})
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://{expected}':return self.reply(403,{'error':'Недопустимый источник запроса.'})
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=60*1024*1024:return self.reply(400,{'error':'Общий размер файлов должен быть не больше 60 МБ.'})
            body=self.rfile.read(length);p=urllib.parse.urlparse(self.path).path
            if p=='/api/analyze':
                ctype=self.headers.get('Content-Type','')
                if not ctype.startswith('multipart/form-data'):raise ValueError('Не найдены загруженные файлы.')
                msg=BytesParser(policy=default).parsebytes(('Content-Type: '+ctype+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body);files=[]
                for part in msg.iter_parts():
                    name=part.get_filename()
                    if name:
                        if not name.lower().endswith('.xlsx'):raise ValueError('Можно загружать только XLSX.')
                        files.append((Path(name).name,part.get_payload(decode=True)))
                if not files:raise ValueError('Выберите хотя бы один XLSX.')
                if len(files)>30:raise ValueError('За один раз можно загрузить до 30 файлов.')
                data=analyze(files);jid=secrets.token_hex(12)
                with LOCK:
                    if len(JOBS)>=10:JOBS.pop(next(iter(JOBS)))
                    JOBS[jid]=data
                summary={k:data[k] for k in ['warnings','errors','sources','tts','unknownCount']}
                summary.update(id=jid,dailyCount=len(data['daily']),collectorCount=len(data['collectors']),appealCount=len(data['appeals']),fileCount=len(files),dates=sorted({r['date'] for r in [*data['daily'],*data['appeals'],*data['collectors']]}),nameDirectory=directory_view(data,NAMES.read()))
                return self.reply(200,summary)
            payload=json.loads(body);data=JOBS.get(payload.get('id'))
            if p=='/api/collector-names':return self.reply(200,directory_view(data,NAMES.read()))
            if p=='/api/collector-names/save':
                state=NAMES.save(payload.get('entries'),payload.get('revision'),sightings(data))
                return self.reply(200,directory_view(data,state))
            if p=='/api/collector-names/remove':
                state=NAMES.save([],payload.get('revision'),remove=payload.get('collectorId'))
                return self.reply(200,directory_view(data,state))
            if p=='/api/open':
                folder=RUNS.get(payload.get('run'))
                if not folder:raise ValueError('Папка отчёта не найдена.')
                os.startfile(folder);return self.reply(200,{'ok':True})
            if not data:raise ValueError('Сначала загрузите выгрузки заново.')
            data=apply_directory(data,NAMES.read())
            if p=='/api/preview':
                if payload.get('options',{}).get('mode')=='details':
                    from details import detail_selection
                    return self.reply(200,detail_selection(data,payload['options']))
                options=payload.get('options',{});groups,dates,apps=select(data,options)
                return self.reply(200,{'groups':groups,'dates':dates,'appeals':len(apps),'orders':sum(g['orders'] for g in groups),'late':sum(g['late'] for g in groups),**selection_inputs(data,options)[2]})
            if p=='/api/generate':
                rid=dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'_'+secrets.token_hex(3);folder=RESULTS/rid
                audit=generate(data,payload.get('options',{}),folder);RUNS[rid]=folder
                return self.reply(200,{'run':rid,'audit':audit,'archive':f'/files/{rid}/'+urllib.parse.quote('Все результаты.zip'),'excel':f'/files/{rid}/'+urllib.parse.quote('Отчёт.xlsx'),'images':[{'name':f.name,'url':f'/files/{rid}/'+urllib.parse.quote('Изображения/'+f.name)} for f in sorted((folder/'Изображения').glob('*.png'))]})
            self.reply(404,{'error':'Команда не найдена.'})
        except (ValueError,KeyError) as e:self.reply(400,{'error':str(e)})
        except Exception as e:
            (ROOT/'Ошибка.txt').write_text(traceback.format_exc(),encoding='utf-8');self.reply(500,{'error':'Не удалось завершить обработку. Подробности сохранены в «Ошибка.txt» рядом с приложением.'})
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--port',type=int,default=0);args=parser.parse_args()
    state=ROOT/'.server.json'
    if not args.port and state.exists():
        try:
            import urllib.request
            info=json.loads(state.read_text());url=info['url']
            with urllib.request.urlopen(url+'/api/health',timeout=1) as r:valid=json.load(r).get('app')==APP_ID
            if valid:
                if not args.no_browser:webbrowser.open(url)
                return
        except Exception:pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);url=f'http://127.0.0.1:{server.server_port}';state.write_text(json.dumps({'url':url}),encoding='utf-8')
    print(url,flush=True)
    if not args.no_browser:threading.Timer(.4,lambda:webbrowser.open(url)).start()
    server.serve_forever()
if __name__=='__main__':main()
