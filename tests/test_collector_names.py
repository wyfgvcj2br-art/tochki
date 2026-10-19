import copy,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from collector_names import NameDirectory,collector_id,directory_view,apply_directory,sightings
from details import detail_selection
from engine import generate
import test_details as fixtures


class NameTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=fixtures.TMP);self.addCleanup(self.tmp.cleanup)
        self.directory=NameDirectory(self.tmp.name)
        fixture=fixtures.DetailTests();fixture.setUp();self.data=fixture.data();self.opts=fixture.opts

    def save(self,entries):
        return self.directory.save(entries,self.directory.read()['revision'],sightings(self.data))

    def test_normalize_id_and_hide_zero(self):
        self.assertEqual([collector_id(x) for x in [2,2.0,'002.00',0,None]],['2','2','2','0',''])
        self.data['collectors']+= [{**self.data['collectors'][1],'collectorId':'0'}]
        view=directory_view(self.data,self.directory.read())
        self.assertEqual([r['id'] for r in view['pending']],['2'])
        with self.assertRaises(ValueError):self.save([{'id':'0','name':'Демо Сборщик'}])
        self.assertFalse(self.directory.path.exists())

    def test_context_known_hint_multiple_stores_and_missing_id(self):
        row=self.data['collectors'][1]
        self.data['collectors'] += [{**row,'tt':'9002_Демо','name':'Подсказка Сборщик'}, {**row,'collectorId':''}]
        view=directory_view(self.data,self.directory.read())
        item=next(r for r in view['pending'] if r['id']=='2')
        self.assertEqual(item['tts'],['9001_Демо','9002_Демо']);self.assertEqual(item['knownNames'],['Подсказка Сборщик'])
        self.assertFalse(next(r for r in view['pending'] if not r['id'])['bindable'])
        self.assertFalse(self.directory.path.exists())

    def test_restart_edit_backup_stale_revision(self):
        old=self.save([{'id':'002.0','name':'Демо   Сборщик'}]);blob=self.directory.path.read_bytes()
        self.assertEqual(NameDirectory(self.tmp.name).read(),old)
        self.assertEqual(old['entries']['2']['name'],'Демо Сборщик')
        self.save([{'id':'2','name':'Исправленный Сборщик'}])
        self.assertEqual(self.directory.path.with_suffix('.json.bak').read_bytes(),blob)
        with self.assertRaisesRegex(ValueError,'изменился'):self.directory.save([{'id':'2','name':'Старое Имя'}],old['revision'])
        self.assertEqual(self.directory.read()['entries']['2']['name'],'Исправленный Сборщик')

    def test_invalid_update_and_corruption_do_not_overwrite(self):
        self.save([{'id':'2','name':'Демо Сборщик'}]);blob=self.directory.path.read_bytes()
        for name in ['123','N/A','ФИО не указано','', '<script>']:
            with self.assertRaises(ValueError):self.save([{'id':'2','name':name}])
            self.assertEqual(self.directory.path.read_bytes(),blob)
        self.directory.path.write_bytes(b'{broken')
        with self.assertRaisesRegex(ValueError,'резервную'):self.directory.read()
        with self.assertRaises(ValueError):self.directory.save([], 'old')
        self.assertEqual(self.directory.path.read_bytes(),b'{broken')

    def test_atomic_failure_preserves_old_file(self):
        self.save([{'id':'2','name':'Демо Сборщик'}]);blob=self.directory.path.read_bytes()
        original=self.directory.atomic_write
        def fail_main(path,data):
            if path==self.directory.path:raise OSError('disk full')
            original(path,data)
        with patch.object(self.directory,'atomic_write',side_effect=fail_main):
            with self.assertRaises(OSError):self.save([{'id':'2','name':'Другое Имя'}])
        self.assertEqual(self.directory.path.read_bytes(),blob)

    def test_overlay_only_missing_preserves_raw_metrics_and_exported_name(self):
        original=copy.deepcopy(self.data);state=self.save([{'id':'2','name':'Демо Сборщик'},{'id':'1','name':'Другое Имя'}])
        resolved=apply_directory(self.data,state);preview=detail_selection(resolved,self.opts)
        self.assertEqual(self.data,original)
        self.assertEqual((preview['orders'],preview['late'],preview['collectorCount']),(100,7,2))
        self.assertEqual(preview['unknownCollectors'],0)
        self.assertEqual(resolved['collectors'][0]['name'],'Первый Сборщик')
        self.assertTrue(any('Заполненное ФИО' in w for w in preview['warnings']))
        state=self.save([{'id':'2','name':'Исправленное Имя'}])
        self.assertEqual(apply_directory(self.data,state)['collectors'][1]['name'],'Исправленное Имя')
        state=self.directory.save([],state['revision'],remove='2')
        self.assertEqual(apply_directory(self.data,state)['collectors'][1]['name'],'')

    def test_mapped_and_export_name_same_day_prioritize_export(self):
        row=self.data['collectors'][1]
        self.data['collectors'].append({**row,'orders':1,'name':'Имя Извыгрузки'})
        state=self.save([{'id':'2','name':'Ручное Имя'}])
        for rows in [self.data['collectors'],list(reversed(self.data['collectors']))]:
            p=detail_selection(apply_directory({**self.data,'collectors':rows},state),self.opts)
            person=next(r for r in p['groups'][0]['days'][0]['collectors'] if r['collectorId']=='2')
            self.assertEqual(person['name'],'Имя Извыгрузки');self.assertEqual(person['orders'],61)

    def test_zero_hidden_from_rows_and_totals_including_numeric_zero(self):
        self.data['collectors'].append({**self.data['collectors'][1],'collectorId':0,'orders':10,'late':2})
        p=detail_selection(self.data,self.opts)
        self.assertEqual(p['hiddenIdZero'],{'rows':1,'orders':10,'late':2})
        self.assertEqual((p['orders'],p['late'],p['collectorCount']),(100,7,2))
        self.assertTrue(any('ID 0 скрыт' in w for w in p['warnings']))
        self.assertEqual(len(self.data['collectors']),3)

    def test_numeric_zero_from_xlsx_and_all_hidden_day(self):
        fixture=fixtures.DetailTests();fixture.setUp()
        fixture.people[2][2]=0
        data=fixture.data();self.assertEqual(data['collectors'][1]['collectorId'],'0')
        p=detail_selection(data,self.opts)
        self.assertEqual(p['hiddenIdZero'],{'rows':1,'orders':60,'late':0})
        self.assertEqual((p['orders'],p['late'],p['groups'][0]['days'][0]['pct']),(40,7,7/40))
        data['collectors'][0]['collectorId']='0'
        p=detail_selection(data,self.opts)
        self.assertEqual((p['orders'],p['late'],p['collectorCount']),(0,0,0))
        self.assertIsNone(p['groups'][0]['days'][0]['pct'])

    def test_excel_and_audit_have_confirmed_name_and_unchanged_metrics(self):
        state=self.save([{'id':'2','name':'Демо Сборщик'}])
        folder=Path(self.tmp.name)/'report';audit=generate(apply_directory(self.data,state),self.opts,folder)
        self.assertEqual(audit['nameBindingsUsed'],[{'id':'2','name':'Демо Сборщик'}])
        w=openpyxl.load_workbook(folder/'Отчёт.xlsx');rows=list(w.active.values);w.close()
        self.assertIn(('Демо Сборщик',60,0,0),rows)
        self.assertEqual((audit['orders'],audit['late']),(100,7))
        self.assertEqual(len(list((folder/'Изображения').glob('*.png'))),1)


if __name__=='__main__':unittest.main()
