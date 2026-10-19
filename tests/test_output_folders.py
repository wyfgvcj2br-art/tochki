import importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from output_folders import resolve_folder,folder_setting,check_folder

TMP=Path(__file__).resolve().parents[1]/'.cache/tests';TMP.mkdir(parents=True,exist_ok=True)


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=TMP);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.app=self.root/'portable';self.app.mkdir()

    def test_default_and_portable_move(self):
        self.assertEqual(resolve_folder(self.app),self.app/'Результаты')
        setting=folder_setting(self.app,self.app/'Мои отчёты')
        self.assertTrue(setting['relative'])
        self.assertEqual(resolve_folder(self.root/'moved',setting),self.root/'moved/Мои отчёты')

    def test_external_path_stays_absolute_and_cannot_escape_relative_app(self):
        chosen=self.root/'Отчёты по ТТ';chosen.mkdir()
        setting=folder_setting(self.app,chosen)
        self.assertFalse(setting['relative']);self.assertEqual(resolve_folder(self.app,setting),chosen)
        self.assertEqual(resolve_folder(self.root/'moved',setting),chosen)
        with self.assertRaises(ValueError):resolve_folder(self.app,{'path':'../outside','relative':True})
        with self.assertRaises(ValueError):resolve_folder(self.app,{'path':'outside','relative':False})

    def test_write_probe_and_unavailable_destination(self):
        chosen=self.root/'Отчёты';check_folder(chosen,create=True)
        self.assertEqual(list(chosen.iterdir()),[])
        file=self.root/'file.txt';file.write_text('keep')
        with self.assertRaisesRegex(ValueError,'другую папку'):check_folder(file)
        self.assertEqual(file.read_text(),'keep')
        with patch('output_folders.tempfile.NamedTemporaryFile',side_effect=PermissionError('read-only')):
            with self.assertRaisesRegex(ValueError,'другую папку'):check_folder(chosen)
        self.assertEqual(list(chosen.iterdir()),[])

    def desktop(self):
        spec=importlib.util.spec_from_file_location('test_desktop_bridge',Path(__file__).resolve().parents[1]/'app/desktop.py')
        mod=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ),patch.object(Path,'mkdir'):spec.loader.exec_module(mod)
        mod.APP=self.app;mod.DATA=self.app/'Data';mod.DATA.mkdir()
        return mod,mod.DesktopAPI()

    def test_native_selection_saved_and_reused_on_restart_preserves_other_settings(self):
        mod,api=self.desktop();folder=self.root/'Выбранная папка';folder.mkdir()
        (mod.DATA/'settings.json').write_text(json.dumps({'theme':'dark','options':{'codes':['9001']}}))
        server=types.SimpleNamespace(RESULTS=self.app/'Результаты')
        api._window=Mock();api._window.create_file_dialog.return_value=(str(folder),)
        with patch.dict(sys.modules,{'server':server,'webview':types.SimpleNamespace(FileDialog=types.SimpleNamespace(FOLDER=20))}):
            result=api.choose_output_folder()
            self.assertEqual(result,{'path':str(folder)});self.assertEqual(server.RESULTS,folder)
            settings=mod.DesktopAPI().load_settings()
            self.assertEqual(settings['theme'],'dark');self.assertEqual(settings['options']['codes'],['9001'])
            self.assertEqual(resolve_folder(self.app,settings['outputFolder']),folder)
            self.assertEqual(api.get_output_folder()['path'],str(folder))

    def test_cancel_and_invalid_choice_preserve_previous_folder(self):
        mod,api=self.desktop();api._save('theme','dark');before=(mod.DATA/'settings.json').read_bytes()
        server=types.SimpleNamespace(RESULTS=self.app/'Результаты');api._window=Mock()
        with patch.dict(sys.modules,{'server':server,'webview':types.SimpleNamespace(FileDialog=types.SimpleNamespace(FOLDER=20))}):
            api._window.create_file_dialog.return_value=None
            self.assertTrue(api.choose_output_folder()['cancelled'])
            api._window.create_file_dialog.return_value=(str(self.root/'missing'),)
            self.assertIn('error',api.choose_output_folder())
            self.assertEqual(server.RESULTS,self.app/'Результаты')
            self.assertEqual((mod.DATA/'settings.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
