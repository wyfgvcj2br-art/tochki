"""Runs as the same standard user after uninstallation, without launching the app."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from app_paths import paths
locations=paths(app=Path(sys.argv[1]),mode='installed')
assert json.loads((locations.data/'settings.json').read_text(encoding='utf-8'))['theme']=='light'
assert (locations.data/'collector-names.json').is_file()
assert (locations.data/'collector-names.json.bak').is_file()
assert (locations.data/'survival.txt').read_text(encoding='utf-8')=='сохранить'
assert (locations.reports.parent/'Проверка отчётов с пробелами/survival.txt').read_text(encoding='utf-8')=='сохранить'
print('User settings, directory, backup and reports survived uninstall.')
