"""Render synthetic examples for review; never reads working reports or personal data."""
from __future__ import annotations
import base64
import copy
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from engine import picture
from details import detail_picture

def main():
    output=Path(sys.argv[1]) if len(sys.argv)>1 else Path('.cache/png-previews')
    output.mkdir(parents=True,exist_ok=True)
    dates=['2026-11-16','2026-11-22']
    days=[
        {'date':'2026-11-16','orders':250,'late':10,'pct':.04},
        {'date':'2026-11-17','orders':200,'late':12,'pct':.06},
        {'date':'2026-11-18','orders':300,'late':24,'pct':.08},
        {'date':'2026-11-19','orders':200,'late':25,'pct':.125},
        {'date':'2026-11-20','orders':0,'late':0,'pct':None},
    ]
    appeals=[
        {'date':'2026-11-16','name':'Иванов Иван Иванович','count':2},
        {'date':'2026-11-18','name':'Демонстрационный Сотрудник С Очень Длинным Именем Для Проверки Переноса Строк','count':1},
    ]
    group={'tt':'9001 · Демонстрационная торговая точка','orders':950,'late':71,'days':days,'appeals':appeals}
    picture(copy.deepcopy(group),dates,output/'stores.png',.06,.10)
    picture(copy.deepcopy(group),dates,output/'appeals.png',.06,.10,True)
    detail={'tt':group['tt'],'orders':200,'late':14,'days':[
        {'date':'2026-11-17','orders':200,'late':14,'pct':.07,'collectors':[
            {'name':'Демонстрационный Сотрудник С Очень Длинным Именем Для Проверки Переноса Строк','orders':80,'late':10,'pct':.125},
            {'name':'Петров Пётр Петрович','orders':100,'late':4,'pct':.04},
            {'name':'','orders':20,'late':0,'pct':0},
        ]},
    ]}
    detail_picture(detail,dates,output/'collectors.png')
    # Optional inline previews for environments that cannot download artifacts locally.
    if '--inline' in sys.argv:
        import io
        for name in ('stores','collectors','appeals'):
            with Image.open(output/(name+'.png')) as im:
                im.thumbnail((1000,1600),Image.Resampling.LANCZOS)
                stream=io.BytesIO();im.save(stream,format='PNG')
                print('PREVIEW_'+name+'='+base64.b64encode(stream.getvalue()).decode())

if __name__=='__main__': main()
