"""Fail before building if alternate Windows logon/profile setup is unusable."""
import ctypes
import os
import sys
from pathlib import Path
from windows_test_environment import restore_user_environment
restore_user_environment()
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from app_paths import paths
assert not ctypes.windll.shell32.IsUserAnAdmin()
profile=Path(os.environ['USERPROFILE']).resolve()
assert any(ord(char)>127 for char in profile.name),profile
locations=paths(mode='installed')
assert locations.data.resolve().is_relative_to(profile),str(locations.data)
locations.ensure()
probe=locations.data/'environment-probe.txt'
probe.write_text('Проверка кириллицы',encoding='utf-8')
assert probe.read_text(encoding='utf-8')=='Проверка кириллицы'
probe.unlink()
print('Native non-admin Cyrillic user environment verified: '+str(profile))
