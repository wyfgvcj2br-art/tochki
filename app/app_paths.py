"""All resource and writable locations, independent of the process working directory."""
from __future__ import annotations
import ctypes
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

FOLDERS = {'fonts': 'FD228CB7-AE11-4AE3-864C-16F3910AB8FE', 'local': 'F1B32785-6FBA-4FCF-9D55-7B8E7F157091',
           'documents': 'FDD39AD0-238F-46AF-ADB4-6C85480369C7'}

def known_folder(name):
    if os.name != 'nt':
        raise OSError('Windows Known Folders API is required.')
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID(FOLDERS[name]).bytes_le)
    result = ctypes.c_wchar_p()
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_wchar_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    hr = shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(result))
    if hr < 0:
        raise OSError(f'SHGetKnownFolderPath({name}): HRESULT 0x{hr & 0xffffffff:08x}')
    try:
        return Path(result.value)
    finally:
        ole = ctypes.WinDLL('ole32')
        ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))

@dataclass(frozen=True)
class AppPaths:
    app: Path
    resources: Path
    mode: str
    data: Path
    webview: Path
    logs: Path
    reports: Path

    def ensure(self):
        for path in (self.data, self.webview, self.logs):
            path.mkdir(parents=True, exist_ok=True)

def paths(app=None, resources=None, mode=None, folder_api=known_folder):
    app = Path(app or (Path(sys.executable).parent if getattr(sys, 'frozen', False)
                       else Path(__file__).resolve().parent)).resolve()
    resources = Path(resources or Path(__file__).resolve().parent).resolve()
    if mode is None:
        marker = app / 'distribution.json'
        if marker.exists():
            metadata = json.loads(marker.read_text(encoding='utf-8'))
            if metadata.get('distribution') != 'installed':
                raise ValueError('Повреждён файл distribution.json. Переустановите приложение.')
            mode = 'installed'
        else:
            mode = 'portable'  # Preserves source development and existing portable behavior.
    if mode == 'installed':
        local = folder_api('local') / 'Tochki'
        return AppPaths(app, resources, mode, local/'Data', local/'WebView',
                        local/'Logs', folder_api('documents')/'Точки'/'Результаты')
    if mode != 'portable':
        raise ValueError('Неизвестный формат приложения.')
    return AppPaths(app, resources, mode, app/'Data', app/'Data'/'WebView',
                    app/'Data'/'Logs', app/'Результаты')

def result_folder(locations, setting=None):
    from output_folders import resolve_folder
    if not setting:
        return locations.reports
    if locations.mode == 'installed' and setting.get('relative') is True:
        raise ValueError('В установленной версии нужен полный путь папки отчётов.')
    return resolve_folder(locations.app, setting)

def result_setting(locations, path):
    from output_folders import folder_setting
    path = Path(path).resolve()
    if locations.mode == 'installed':
        return {'path': str(path), 'relative': False}
    return folder_setting(locations.app, path)

def product_version(resources=None):
    root=Path(resources or Path(__file__).resolve().parent)
    for file in (root/'VERSION',root.parent/'VERSION'):
        if file.is_file():
            return file.read_text(encoding='utf-8').strip()
    raise ValueError('Не найден VERSION. Переустановите приложение.')
