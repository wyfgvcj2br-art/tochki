from __future__ import annotations
import ctypes,json,os,sys,threading,traceback,subprocess
from pathlib import Path
from output_folders import resolve_folder,folder_setting,check_folder
APP=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
DATA=APP/'Data'
try:DATA.mkdir(parents=True,exist_ok=True)
except OSError:
    ctypes.windll.user32.MessageBoxW(None,'Распакуйте приложение в папку с правом записи, например на рабочий стол или USB-накопитель.','Точки Portable',16)
    raise
os.environ['TT_DATA_DIR']=str(DATA)
os.environ['TT_OUTPUT_DIR']=str(APP/'Результаты')
class DesktopAPI:
    def __init__(self):self._window=None;self._expanded=False
    def minimize(self):self._window.minimize()
    def maximize(self):
        if self._expanded:self._window.restore()
        else:self._window.maximize()
        self._expanded=not self._expanded
    def close(self):self._window.destroy()
    def load_settings(self):
        try:return json.loads((DATA/'settings.json').read_text(encoding='utf-8'))
        except Exception:return {}
    def _save(self,kind,value):
        with settings_lock:
            settings=self.load_settings();settings[kind]=value
            (DATA/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
        return True
    def save_theme(self,value):return self._save('theme','light' if value=='light' else 'dark')
    def save_options(self,value):
        if not isinstance(value,dict):return False
        keys={'codes','good','bad','excludeUnknown','journal','outline','mode'}
        return self._save('options',{k:v for k,v in value.items() if k in keys})
    def get_output_folder(self):
        import server
        return {'path':str(server.RESULTS)}
    def choose_output_folder(self):
        import server,webview
        try:
            current=server.RESULTS
            chosen=self._window.create_file_dialog(webview.FileDialog.FOLDER,directory=str(current if current.is_dir() else APP))
            if not chosen:return {'cancelled':True,'path':str(current)}
            path=check_folder(chosen[0])
            self._save('outputFolder',folder_setting(APP,path))
            server.RESULTS=path
            return {'path':str(path)}
        except (ValueError,OSError) as error:return {'error':str(error)}
    def open_output_folder(self):
        import server
        try:
            path=server.RESULTS
            if not path.is_dir():raise ValueError('Папка отчётов недоступна. Выберите другую папку.')
            os.startfile(path)
            return {'ok':True}
        except (ValueError,OSError) as error:return {'error':str(error)}
settings_lock=threading.Lock()
def main():
    try:
        import webview
        import server
        from http.server import ThreadingHTTPServer
        api=DesktopAPI()
        server.RESULTS=resolve_folder(APP,api.load_settings().get('outputFolder'))
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SaudadeMeow.Tochki.Portable.2.1')
        runtime_root=APP/'WebView2'
        runtimes=sorted(runtime_root.rglob('msedgewebview2.exe')) if runtime_root.is_dir() else []
        if not runtimes:raise RuntimeError('Нет встроенного WebView2. Распакуйте весь portable-архив, а не только EXE.')
        runtime=runtimes[0].parent
        webview.settings['WEBVIEW2_RUNTIME_PATH']=str(runtime)
        os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER']=str(runtime)
        # Microsoft Fixed Version v120+ requires read/execute ACLs for AppContainers on Windows 10.
        if sys.getwindowsversion().build<22000:
            subprocess.run(['icacls',str(runtime),'/grant','*S-1-15-2-2:(OI)(CI)(RX)','/grant','*S-1-15-2-1:(OI)(CI)(RX)'],creationflags=subprocess.CREATE_NO_WINDOW,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{http.server_port}'
        state={'url':url,'pid':os.getpid(),'app':str(APP),'runtime':str(runtime),'mode':'portable','ready':False}
        statefile=DATA/'desktop-state.json'
        statefile.write_text(json.dumps(state),encoding='utf-8')
        webview.settings['ALLOW_DOWNLOADS']=True
        window=webview.create_window('Точки · Prod. by Saudade_meow',url=url,js_api=api,width=1380,height=920,min_size=(1000,700),frameless=True,easy_drag=False,shadow=True,background_color='#090F18',text_select=True)
        api._window=window
        def loaded():
            state['ready']=True
            statefile.write_text(json.dumps(state),encoding='utf-8')
        window.events.loaded+=loaded
        window.events.closed+=lambda:http.shutdown()
        icon=Path(__file__).resolve().parent/'Точки.ico'
        webview.start(gui='edgechromium',private_mode=False,storage_path=str(DATA/'WebView'),icon=str(icon),debug=False)
        http.server_close()
    except Exception:
        error=traceback.format_exc();(DATA/'Ошибка.txt').write_text(error,encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None,f'Не удалось запустить «Точки».\nПодробности: {DATA / "Ошибка.txt"}','Точки',16)
        raise
if __name__=='__main__':main()
