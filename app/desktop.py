from __future__ import annotations
import ctypes,dataclasses,hashlib,json,os,sys,threading,traceback,subprocess
from pathlib import Path
from app_paths import paths,result_folder,result_setting
from settings_store import read_settings,save_settings,atomic_write
from output_folders import check_folder

PATHS=paths()
APP=PATHS.app
DATA=PATHS.data
settings_lock=threading.RLock()

def current_paths():
    return dataclasses.replace(PATHS,app=APP,data=DATA)

class DesktopAPI:
    def __init__(self):self._window=None;self._expanded=False;self._migration_review=None;self._migration_token=None
    def minimize(self):self._window.minimize()
    def maximize(self):
        if self._expanded:self._window.restore()
        else:self._window.maximize()
        self._expanded=not self._expanded
    def close(self):self._window.destroy()
    def load_settings(self):return read_settings(DATA/'settings.json')
    def _save(self,kind,value):
        with settings_lock:
            settings=self.load_settings();settings[kind]=value
            save_settings(DATA/'settings.json',settings)
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
            chosen=self._window.create_file_dialog(webview.FileDialog.FOLDER,directory=str(current if current.is_dir() else PATHS.reports.parent))
            if not chosen:return {'cancelled':True,'path':str(current)}
            path=check_folder(chosen[0])
            self._save('outputFolder',result_setting(current_paths(),path))
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

    def get_app_info(self):
        from app_paths import product_version
        return {'version':product_version(PATHS.resources),'mode':PATHS.mode}
    def get_migration_status(self):
        from portable_migration import migration_status
        return {'available':PATHS.mode=='installed',**(migration_status(DATA) if PATHS.mode=='installed' else {'pending':False})}
    def choose_portable_folder(self):
        import webview
        from portable_migration import preview_import
        try:
            if PATHS.mode!='installed':raise ValueError('Импорт доступен в установленной версии.')
            chosen=self._window.create_file_dialog(webview.FileDialog.FOLDER)
            if not chosen:return {'cancelled':True}
            with settings_lock:
                review=preview_import(chosen[0],DATA)
                import secrets
                self._migration_review=review;self._migration_token=secrets.token_hex(24)
            return {'token':self._migration_token,'source':review['source'],'files':review['files']}
        except (ValueError,OSError) as error:return {'error':str(error)}
    def import_portable(self,token):
        from portable_migration import import_data
        try:
            with settings_lock:
                if PATHS.mode!='installed' or not self._migration_review or token!=self._migration_token:
                    raise ValueError('Сначала выберите и проверьте папку Portable.')
                replace=any(item['replace'] for item in self._migration_review['files'])
                if replace and not self._window.create_confirmation_dialog(
                        'Заменить данные «Точки»?',
                        'В установленной версии уже есть настройки или справочник. Заменить их данными Portable? Текущие файлы будут сохранены в Data/Backups.'):
                    return {'cancelled':True}
                result=import_data(self._migration_review,DATA,confirm_replace=replace)
                self._migration_review=None;self._migration_token=None
                import server
                server.RESULTS=result_folder(current_paths(),self.load_settings().get('outputFolder'))
                return result
        except (ValueError,OSError) as error:return {'error':str(error)}
    def skip_migration(self):
        from portable_migration import skip_import
        if PATHS.mode!='installed':return {'ok':True}
        with settings_lock:return skip_import(DATA)

def configure_windows():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError,OSError):pass
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SaudadeMeow.Tochki')

def main():
    http=None;thread=None;statefile=None;state={};mutex=None
    try:
        PATHS.ensure()
        configure_windows()
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        mutex=kernel.CreateMutexW(None,False,'Local\\Tochki-'+hashlib.sha256(str(DATA).encode()).hexdigest()[:24])
        if ctypes.get_last_error()==183:
            ctypes.windll.user32.MessageBoxW(None,'«Точки» уже запущены для этого профиля.','Точки',64)
            return
        os.environ['TT_DATA_DIR']=str(DATA)
        os.environ['TT_OUTPUT_DIR']=str(PATHS.reports)
        os.environ['TT_LOG_DIR']=str(PATHS.logs)
        # Runtime web traffic is local. Disable background services and proxy all
        # non-loopback browser requests to an unused local port, including offline use.
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=(
            '--disable-background-networking --disable-component-update --disable-sync '
            '--disable-domain-reliability --no-first-run --no-default-browser-check '
            '--proxy-server=http://127.0.0.1:9 --proxy-bypass-list=localhost;127.0.0.1')
        import webview
        import server
        from http.server import ThreadingHTTPServer
        api=DesktopAPI()
        try:server.RESULTS=result_folder(PATHS,api.load_settings().get('outputFolder'))
        except ValueError:
            # Keep malformed settings intact; the UI reports the error and offers import.
            server.RESULTS=PATHS.reports
        runtime_root=APP/'WebView2'
        runtimes=sorted(runtime_root.rglob('msedgewebview2.exe')) if runtime_root.is_dir() else []
        if len(runtimes)!=1:raise RuntimeError('Встроенный WebView2 отсутствует или повреждён. Переустановите приложение либо распакуйте полный Portable-архив.')
        runtime=runtimes[0].parent
        webview.settings['WEBVIEW2_RUNTIME_PATH']=str(runtime)
        os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER']=str(runtime)
        if PATHS.mode=='portable' and sys.getwindowsversion().build<22000:
            subprocess.run(['icacls',str(runtime),'/grant','*S-1-15-2-2:(OI)(CI)(RX)','/grant','*S-1-15-2-1:(OI)(CI)(RX)'],creationflags=subprocess.CREATE_NO_WINDOW,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        http.daemon_threads=True
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{http.server_port}'
        state={'url':url,'pid':os.getpid(),'app':str(APP),'runtime':str(runtime),'mode':PATHS.mode,
               'data':str(DATA),'webview':str(PATHS.webview),'logs':str(PATHS.logs),
               'reports':str(server.RESULTS),'ready':False}
        statefile=(DATA if PATHS.mode=='portable' else PATHS.logs)/'desktop-state.json'
        def write_state():atomic_write(statefile,json.dumps(state,ensure_ascii=False).encode('utf-8'))
        write_state()
        webview.settings['ALLOW_DOWNLOADS']=True
        window=webview.create_window('Точки · Prod. by Saudade_meow',url=url,js_api=api,width=1380,height=920,min_size=(720,520),frameless=True,easy_drag=False,shadow=True,background_color='#090F18',text_select=True)
        api._window=window
        def loaded():
            state['ready']=True
            try:state['hwnd']=int(window.native.Handle.ToInt64())
            except (AttributeError,TypeError):pass
            write_state()
        window.events.loaded+=loaded
        icon=PATHS.resources/'Точки.ico'
        webview.start(gui='edgechromium',private_mode=False,storage_path=str(PATHS.webview),icon=str(icon),debug=False)
    except Exception:
        error=traceback.format_exc()
        try:
            PATHS.logs.mkdir(parents=True,exist_ok=True)
            atomic_write(PATHS.logs/'Ошибка.txt',error.encode('utf-8'))
            message=f'Не удалось запустить «Точки».\nПодробности: {PATHS.logs / "Ошибка.txt"}'
        except OSError:message='Не удалось открыть папку данных «Точки». Проверьте доступ к профилю Windows.'
        ctypes.windll.user32.MessageBoxW(None,message,'Точки',16)
        raise
    finally:
        if http:
            http.shutdown();http.server_close()
        if thread:thread.join(timeout=5)
        if statefile and state:
            state['ready']=False
            try:atomic_write(statefile,json.dumps(state,ensure_ascii=False).encode('utf-8'))
            except OSError:pass
        if mutex:
            ctypes.windll.kernel32.CloseHandle.argtypes=[ctypes.c_void_p]
            ctypes.windll.kernel32.CloseHandle(mutex)

if __name__=='__main__':main()
