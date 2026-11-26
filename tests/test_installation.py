import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from app_paths import paths,result_folder,result_setting,known_folder
from portable_migration import preview_import,import_data,migration_status,skip_import
from settings_store import read_settings,save_settings,atomic_write

class InstallationPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.app=self.root/'Program Files'/'Точки с пробелами';self.app.mkdir(parents=True)
        self.local=self.root/'Перенаправленный профиль'/'Local'
        self.documents=self.root/'Другая папка документов'
    def layout(self,mode='installed'):
        return paths(self.app,self.app/'_internal',mode,lambda name:self.local if name=='local' else self.documents)
    def test_installed_paths_use_redirected_known_folders_and_never_executable_directory(self):
        locations=self.layout()
        locations.ensure()
        self.assertEqual(locations.data,self.local/'Tochki/Data')
        self.assertEqual(locations.webview,self.local/'Tochki/WebView')
        self.assertEqual(locations.logs,self.local/'Tochki/Logs')
        self.assertEqual(locations.reports,self.documents/'Точки/Результаты')
        self.assertEqual(list(self.app.iterdir()),[])
        self.assertEqual(result_folder(locations),locations.reports)
    def test_installed_chosen_folder_is_absolute_even_inside_app(self):
        locations=self.layout()
        chosen=self.root/'Выбранные отчёты'
        setting=result_setting(locations,chosen)
        self.assertFalse(setting['relative'])
        self.assertEqual(result_folder(locations,setting),chosen)
        with self.assertRaises(ValueError):result_folder(locations,{'path':'Data','relative':True})
    def test_portable_is_independent_of_cwd_and_keeps_relative_move(self):
        locations=self.layout('portable')
        chosen=self.app/'Мои отчёты'
        setting=result_setting(locations,chosen)
        self.assertEqual(setting,{'path':'Мои отчёты','relative':True})
        moved=paths(self.root/'Перемещённая папка',mode='portable')
        self.assertEqual(result_folder(moved,setting),moved.app/'Мои отчёты')
    def test_distribution_marker_selects_installed_mode(self):
        (self.app/'distribution.json').write_text('{"distribution":"installed"}')
        locations=paths(self.app,folder_api=lambda name:self.local if name=='local' else self.documents)
        self.assertEqual(locations.mode,'installed')
    @unittest.skipUnless(os.name=='nt','Windows Known Folders API')
    def test_real_known_folders_are_absolute(self):
        for name in ('documents','local'):
            self.assertTrue(known_folder(name).is_absolute())

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'Старая Portable';self.old=self.source/'Data';self.old.mkdir(parents=True)
        self.target=self.root/'Профиль'/'Data';self.target.mkdir(parents=True)
        self.names=json.dumps({'version':1,'entries':{'42':{'name':'Иванов Иван','tts':['9001']}}},ensure_ascii=False).encode()
        self.settings={'theme':'light','options':{'codes':['9001'],'good':6,'bad':10,'mode':'details'},'outputFolder':{'path':'Мои отчёты','relative':True}}
        (self.old/'settings.json').write_text(json.dumps(self.settings),encoding='utf-8')
        for name in ('collector-names.json','collector-names.json.bak'):(self.old/name).write_bytes(self.names)
    def plan(self):return preview_import(self.source,self.target)
    def test_import_keeps_source_and_converts_relative_output_to_old_absolute_location(self):
        snapshot={p.name:p.read_bytes() for p in self.old.iterdir()}
        review=self.plan();result=import_data(review,self.target)
        self.assertEqual(len(result['files']),3)
        self.assertEqual(snapshot,{p.name:p.read_bytes() for p in self.old.iterdir()})
        settings=read_settings(self.target/'settings.json')
        self.assertEqual(settings['outputFolder'],{'path':str(self.source/'Мои отчёты'),'relative':False})
        self.assertEqual((self.target/'collector-names.json').read_bytes(),self.names)
        self.assertFalse(migration_status(self.target)['pending'])
    def test_conflict_requires_confirmation_and_creates_exact_backup(self):
        old=b'{"theme":"dark"}';(self.target/'settings.json').write_bytes(old)
        review=self.plan()
        with self.assertRaisesRegex(ValueError,'подтверждения'):import_data(review,self.target)
        self.assertEqual((self.target/'settings.json').read_bytes(),old)
        result=import_data(review,self.target,True)
        self.assertEqual((Path(result['backup'])/'settings.json').read_bytes(),old)
    def test_source_change_after_review_blocks_all_writes(self):
        review=self.plan();(self.old/'settings.json').write_text('{"theme":"dark"}')
        with self.assertRaisesRegex(ValueError,'изменились'):import_data(review,self.target)
        self.assertEqual(list(self.target.iterdir()),[self.target/'.collector-names.lock'])
    def test_destination_change_after_review_blocks_replacement(self):
        review=self.plan();(self.target/'settings.json').write_text('{"theme":"dark"}')
        with self.assertRaisesRegex(ValueError,'изменились'):import_data(review,self.target,True)
        self.assertEqual(read_settings(self.target/'settings.json'),{'theme':'dark'})
    def test_invalid_main_or_backup_aborts_import(self):
        for name in ('settings.json','collector-names.json','collector-names.json.bak'):
            with self.subTest(name=name):
                file=self.old/name;before=file.read_bytes();file.write_bytes(b'{broken')
                with self.assertRaises(ValueError):self.plan()
                self.assertEqual(list(self.target.iterdir()),[])
                file.write_bytes(before)
    def test_invalid_options_or_names_are_rejected(self):
        for value in ({'options':{'codes':'9001'}},{'options':{'good':float('nan')}},{'options':{'mode':'unknown'}},{'theme':'unknown'}):
            (self.old/'settings.json').write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(ValueError):self.plan()
        (self.old/'settings.json').unlink()
        (self.old/'collector-names.json').write_text('{"version":1,"entries":{"0":{"name":"Иван Иванов"}}}',encoding='utf-8')
        with self.assertRaises(ValueError):self.plan()
    def test_path_escape_and_same_source_are_rejected(self):
        self.settings['outputFolder']={'path':'../escape','relative':True}
        (self.old/'settings.json').write_text(json.dumps(self.settings))
        with self.assertRaises(ValueError):self.plan()
        with self.assertRaises(ValueError):preview_import(self.source,self.old)
    def test_partial_failure_restores_preexisting_files_and_marker(self):
        (self.target/'settings.json').write_text('{"theme":"dark"}')
        marker=b'{"version":1,"status":"skipped"}';(self.target/'migration.json').write_bytes(marker)
        review=self.plan();failed=False
        def write(path,blob):
            nonlocal failed
            if Path(path).name=='collector-names.json' and not failed:
                failed=True;raise OSError('simulated full disk')
            return atomic_write(path,blob)
        with patch('portable_migration.atomic_write',side_effect=write):
            with self.assertRaises(OSError):import_data(review,self.target,True)
        self.assertEqual(read_settings(self.target/'settings.json'),{'theme':'dark'})
        self.assertFalse((self.target/'collector-names.json').exists())
        self.assertEqual((self.target/'migration.json').read_bytes(),marker)
    def test_skip_preserves_existing_settings_and_can_import_later(self):
        save_settings(self.target/'settings.json',{'theme':'dark'})
        skip_import(self.target)
        self.assertFalse(migration_status(self.target)['pending'])
        self.assertEqual(read_settings(self.target/'settings.json'),{'theme':'dark'})
        import_data(self.plan(),self.target,True)
        self.assertFalse(migration_status(self.target)['pending'])
    def test_only_whitelisted_files_are_imported(self):
        (self.old/'WebView').mkdir();(self.old/'Ошибка.txt').write_text('old diagnostic')
        (self.old/'desktop-state.json').write_text('{"pid":123}')
        self.assertEqual({x['name'] for x in self.plan()['files']},{'settings.json','collector-names.json','collector-names.json.bak'})
    def test_corrupt_settings_remain_intact(self):
        file=self.target/'settings.json';file.write_bytes(b'invalid')
        with self.assertRaises(ValueError):read_settings(file)
        self.assertEqual(file.read_bytes(),b'invalid')

if __name__=='__main__':unittest.main()
