import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from engine import font, picture
from details import detail_picture
from report_style import wrap, monogram


class PNGDesignTests(unittest.TestCase):
    def test_wrap_preserves_long_names_and_unbroken_store_names(self):
        draw=ImageDraw.Draw(Image.new('RGB',(1,1)))
        for value in ('Демонстрационный Сотрудник С Длинным Именем', '9001_'+'ДлинноеНазвание'*25):
            lines=wrap(draw,value,font(22),250)
            self.assertEqual(''.join(''.join(lines).split()),''.join(value.split()))
            self.assertGreater(len(lines),1)
            self.assertTrue(all(draw.textlength(line,font=font(22))<=250 for line in lines))

    def test_all_modes_render_offline_outside_app_directory_without_mutating_data(self):
        group={'tt':'9001_'+'ДлинноеНазвание'*15,'orders':100,'late':7,
               'days':[{'date':'2026-11-16','orders':100,'late':7,'pct':.07}],
               'appeals':[{'date':'2026-11-16','name':'Длинное Имя '*20,'count':2}]}
        original=copy.deepcopy(group)
        detail={'tt':group['tt'],'orders':100,'late':7,'days':[
            {**group['days'][0],'collectors':[{'name':'Длинное Имя '*20,'orders':100,'late':7,'pct':.07}]}]}
        original_detail=copy.deepcopy(detail)
        dates=['2026-11-16','2026-11-22']
        with tempfile.TemporaryDirectory() as temp:
            old=os.getcwd()
            try:
                os.chdir(temp)
                monogram.cache_clear()
                with patch('urllib.request.urlopen',side_effect=AssertionError('network access')):
                    picture(group,dates,'stores.png',.06,.10)
                    picture(group,dates,'appeals.png',.06,.10,True)
                    detail_picture(detail,dates,'collectors.png')
                for name in ('stores','appeals','collectors'):
                    with Image.open(name+'.png') as image:
                        self.assertEqual(image.width,1500)
                        self.assertEqual(image.mode,'RGB')
                        image.verify()
            finally:
                os.chdir(old)
        self.assertEqual(group,original)
        self.assertEqual(detail,original_detail)


if __name__=='__main__': unittest.main()
