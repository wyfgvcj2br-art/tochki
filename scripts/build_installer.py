"""Build the offline installed payload and a single Inno Setup EXE."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
INNO_VERSION='7.1.1'
INNO_URL='https://github.com/jrsoftware/issrc/releases/download/is-7_1_1/innosetup-7.1.1-x64.exe'
INNO_SHA256='8a5a6711c3766a6e5fb74f280ba0e3551e719ce94538d901fdbd1f8f9920b3f0'

def sha256(path):
    value=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()

def compiler():
    tools=ROOT/'.cache/tools';tools.mkdir(parents=True,exist_ok=True)
    setup=tools/f'innosetup-{INNO_VERSION}-x64.exe'
    if not setup.exists():urllib.request.urlretrieve(INNO_URL,setup)
    if sha256(setup)!=INNO_SHA256:raise RuntimeError('Inno Setup SHA-256 mismatch.')
    folder=tools/f'inno-{INNO_VERSION}'
    iscc=folder/'ISCC.exe'
    if not iscc.exists():
        subprocess.run([str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',f'/DIR={folder}'],check=True)
    if not iscc.is_file():raise RuntimeError('Inno Setup compiler was not installed.')
    return iscc

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--accept-runtime-license',action='store_true')
    parser.add_argument('--runtime-cab',type=Path)
    parser.add_argument('--payload',type=Path,help='Use an already built installed payload')
    args=parser.parse_args()
    if os.name!='nt':raise SystemExit('Installer builds require Windows x64.')
    if not args.accept_runtime_license:raise SystemExit('Read licenses/WEBVIEW2-LICENSE.txt; pass --accept-runtime-license.')
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    payload=args.payload
    if payload is None:
        command=[sys.executable,str(ROOT/'scripts/build_portable.py'),'--format','installed','--accept-runtime-license']
        if args.runtime_cab:command+=['--runtime-cab',str(args.runtime_cab.resolve())]
        subprocess.run(command,check=True,cwd=ROOT)
        payload=out/'installed/Точки'
    payload=payload.resolve()
    data=json.loads((payload/'distribution.json').read_text(encoding='utf-8'))
    version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    if data.get('distribution')!='installed' or data.get('version')!=version:
        raise RuntimeError('Wrong installed payload/version.')
    if any((payload/name).exists() for name in ('Data','Результаты','portable.json')):
        raise RuntimeError('User data or portable marker must not be packaged in the installer.')
    subprocess.run([str(compiler()),f'/DAppVersion={version}',f'/DPayload={payload}',
                    f'/DOutputPath={out}',str(ROOT/'installer/Tochki.iss')],check=True,cwd=ROOT)
    setup=out/f'Tochki-{version}-Setup-x64.exe'
    os.replace(out/'Tochki-Setup-x64.exe',setup)
    checksum=sha256(setup)
    (out/'SHA256SUMS.txt').write_text(f'{checksum}  {setup.name}\n',encoding='ascii')
    manifest={'version':version,'file':setup.name,'sha256':checksum,
              'inno':INNO_VERSION,'inno_setup_sha256':INNO_SHA256,
              'runtime':data['runtime'],'runtime_cab_sha256':data['runtime_cab_sha256'],
              'commit':os.environ.get('GITHUB_SHA'),'python':sys.version}
    (out/'installer-build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('INSTALLER_SHA256='+checksum,flush=True)
    print('Installer ready:',setup,flush=True)

if __name__=='__main__':main()
