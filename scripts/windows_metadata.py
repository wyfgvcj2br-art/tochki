"""Generate PyInstaller resources from VERSION; no elevated execution requested."""
from pathlib import Path

def write_metadata(root,work,version):
    numbers=tuple(int(x) for x in version.split('.'))+(0,)
    if len(numbers)!=4:raise ValueError('VERSION must contain major.minor.patch')
    strings={'CompanyName':'Saudade_meow','FileDescription':'ТОЧКИ · Prod. by Saudade_meow',
             'FileVersion':version+'.0','InternalName':'Tochki','OriginalFilename':'Точки.exe',
             'ProductName':'ТОЧКИ','ProductVersion':version,'LegalCopyright':'Prod. by Saudade_meow'}
    entries=','.join(f'StringStruct({key!r},{value!r})' for key,value in strings.items())
    content=f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers!r},prodvers={numbers!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('041904B0',[{entries}])]),VarFileInfo([VarStruct('Translation',[1049,1200])])])"
    metadata=Path(work)/'version-info.txt';metadata.write_text(content,encoding='utf-8')
    manifest=Path(work)/'app.manifest'
    manifest.write_text((Path(root)/'installer/app.manifest').read_text(encoding='utf-8').replace('2.6.0.0',version+'.0'),encoding='utf-8')
    return metadata,manifest
