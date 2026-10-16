"""Build a Windows x64 folder distribution with its own WebView2 runtime."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME_VERSION='155.0.4283.60'
RUNTIME_URL='https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/ad24dc89-9edc-4b7b-b15a-0d63f8f6ea1d/Microsoft.WebView2.FixedVersionRuntime.155.0.4283.60.x64.cab'
RUNTIME_SHA256='5c5b38df347b2d05b51ef01640ed5ba48511499e4310e71e679e620aaff2ad40'
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-cab',type=Path);parser.add_argument('--accept-runtime-license',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'dist');args=parser.parse_args()
    if os.name!='nt':raise SystemExit('Сборка EXE выполняется на Windows.')
    if not args.accept_runtime_license:raise SystemExit('Прочтите licenses/WEBVIEW2-LICENSE.txt и передайте --accept-runtime-license для включения Runtime.')
    cache=ROOT/'.cache';cache.mkdir(exist_ok=True);cab=args.runtime_cab or cache/f'WebView2-{RUNTIME_VERSION}-x64.cab'
    if not cab.exists():
        print('Downloading official Microsoft Fixed Version Runtime...',flush=True)
        urllib.request.urlretrieve(RUNTIME_URL,cab)
    if digest(cab)!=RUNTIME_SHA256:raise SystemExit('Контрольная сумма WebView2 не совпала. Сборка остановлена.')
    app=ROOT/'app';out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    import PyInstaller.__main__
    argv=[str(app/'desktop.py'),'--name','Точки','--onedir','--windowed','--noconfirm','--distpath',str(out),'--workpath',str(ROOT/'build'),'--specpath',str(ROOT/'build'),'--paths',str(app),'--add-data',str(app/'ui')+os.pathsep+'ui','--add-data',str(app/'Точки.ico')+os.pathsep+'.','--icon',str(app/'Точки.ico'),'--collect-all','webview','--collect-all','clr_loader','--collect-all','pythonnet']
    for name in ['numpy','pandas','scipy','matplotlib','IPython','PyQt5','PyQt6','PySide6','PySide2','webview.platforms.qt','webview.platforms.gtk','webview.platforms.cocoa','webview.platforms.android','webview.platforms.cef','tkinter']:argv+=['--exclude-module',name]
    PyInstaller.__main__.run(argv)
    folder=out/'Точки';runtime=folder/'WebView2';runtime.mkdir(exist_ok=True)
    # Git for Windows also ships expand.exe (a text/tab utility). Use the Windows CAB extractor explicitly.
    expand=Path(os.environ['SystemRoot'])/'System32/expand.exe'
    extract_log=ROOT/'build/runtime-extract.log'
    with open(extract_log,'w',encoding='utf-8') as log:subprocess.run([str(expand),str(cab.resolve()),'-F:*',str(runtime)],check=True,stdout=log,stderr=subprocess.STDOUT)
    if not any(runtime.rglob('msedgewebview2.exe')):
        raise RuntimeError('WebView2 CAB extraction produced no runtime: '+extract_log.read_text(encoding='utf-8',errors='replace'))
    shutil.copytree(ROOT/'licenses',folder/'licenses',dirs_exist_ok=True)
    import importlib.metadata
    for pkg in ['openpyxl','Pillow','pywebview','pythonnet','clr_loader','cffi','pycparser','proxy_tools','bottle','et_xmlfile','typing_extensions','pyinstaller']:
        try:
            dist=importlib.metadata.distribution(pkg)
            for file in dist.files or []:
                if any(part.casefold().startswith(('license','copying','notice')) for part in file.parts) and dist.locate_file(file).is_file():
                    dest=folder/'licenses'/pkg/file.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(dist.locate_file(file),dest)
        except importlib.metadata.PackageNotFoundError:pass
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    if python_license.is_file():shutil.copy2(python_license,folder/'licenses/PYTHON-LICENSE.txt')
    shutil.copy2(ROOT/'PORTABLE.txt',folder/'Прочитать.txt')
    for name in ['Data','Результаты']:(folder/name).mkdir(exist_ok=True)
    version=(ROOT/'VERSION').read_text().strip();manifest={'version':version,'platform':'windows-x64','distribution':'portable-folder','runtime':RUNTIME_VERSION,'runtime_cab_sha256':RUNTIME_SHA256,'settings':'Data/settings.json','results':'Результаты','producer':'Saudade_meow'}
    (folder/'portable.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=out/f'Tochki-Portable-{version}-win-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in folder.rglob('*'):
            if file.is_file():z.write(file,Path('Tochki-Portable')/file.relative_to(folder))
    (out/'SHA256SUMS.txt').write_text(f'{digest(archive)}  {archive.name}\n',encoding='ascii')
    print('Portable ready:',archive,flush=True)
if __name__=='__main__':main()
