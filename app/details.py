"""Collector details for store days whose pooled overdue rate is >=6%."""
from __future__ import annotations
import collections
import datetime as dt
import json
import math
import re
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from PIL import Image, ImageDraw

from engine import DEFAULT_CODES, BLUE, color, font, n, pct

LIMIT=.06


def detail_color(value):
    return '#EDF2F6' if value is None else '#C6EFCE' if value<LIMIT else '#F08080' if value>.10 else '#FCE0E0'


def detail_selection(data,opts):
    if data['errors']:raise ValueError('Сначала устраните ошибки в загруженных данных.')
    selected=set(opts.get('codes',DEFAULT_CODES))
    days=sorted((r for r in data['daily'] if r['code'] in selected),key=lambda r:(r['code'],r['date']))
    if not days:raise ValueError('Для детализации добавьте «Итоговая таблица по магазинам по дням» по выбранным ТТ: по ней определяются дни с просроком от 6% включительно.')
    dates=sorted({r['date'] for r in days})
    if (dt.date.fromisoformat(dates[-1])-dt.date.fromisoformat(dates[0])).days>=7:
        raise ValueError('Детализация: загрузите выгрузку по магазинам максимум за 7 календарных дней, чтобы на каждую ТТ получился один PNG.')
    if not data.get('collectors'):raise ValueError('Добавьте отдельный XLSX «Итоговая таблица по сборщикам по дням».')
    bad=[r for r in days if r['orders'] and r['late']/r['orders']>=LIMIT]
    indexed=collections.defaultdict(list)
    for row in data['collectors']:indexed[row['code'],row['date']].append(row)
    grouped=collections.defaultdict(list);unknown_rows=0;source_rows=0
    for daily in bad:
        key=daily['code'],daily['date'];raw=indexed[key]
        label=f'{daily["tt"]}, {dt.date.fromisoformat(daily["date"]):%d.%m.%Y}'
        if not raw:raise ValueError(f'Нет детализации сборщиков для {label}. Добавьте выгрузку за этот день.')
        orders=sum(r['orders'] for r in raw);late=sum(r['late'] for r in raw)
        if not math.isclose(orders,daily['orders'],rel_tol=1e-10,abs_tol=1e-9) or not math.isclose(late,daily['late'],rel_tol=1e-10,abs_tol=1e-9):
            raise ValueError(f'Не сходится детализация для {label}: по сборщикам {orders:g} заказов / {late:g} просроченных, по ТТ {daily["orders"]:g} / {daily["late"]:g}. Проверьте одинаковые даты и фильтры выгрузок.')
        people={}
        for row in raw:
            # Store aliases and source role/name variants may split one person's day.
            identity=('id',row['collectorId']) if row['collectorId'] else ('name',row['name'])
            person=people.setdefault(identity,{'name':'','collectorId':row['collectorId'],'orders':0,'late':0,'sources':[]})
            if row['name']:
                if person['name'] and person['name']!=row['name']:raise ValueError(f'У одного номера сборщика разные ФИО: {label}. Проверьте исходную выгрузку.')
                person['name']=row['name']
            person['orders']+=row['orders'];person['late']+=row['late'];person['sources'].append(row['source'])
        rows=list(people.values())
        for person in rows:
            person['pct']=person['late']/person['orders'] if person['orders'] else None
            if not person['name']:unknown_rows+=1
        rows.sort(key=lambda r:(-r['late'],-(r['pct'] or 0),r['name'].casefold(),r['collectorId']))
        grouped[daily['code']].append({**daily,'pct':daily['late']/daily['orders'],'collectors':rows,'sourceRows':len(raw)})
        source_rows+=len(raw)
    groups=[]
    for code,records in sorted(grouped.items()):
        groups.append({'code':code,'tt':records[0]['tt'],'days':records,'orders':sum(r['orders'] for r in records),'late':sum(r['late'] for r in records),'appeals':[]})
    warnings=list(data['warnings'])
    normal=sorted({r['code'] for r in days}-set(grouped))
    if normal:warnings.append('Нет дней с просроком от 6% включительно; PNG не требуется для ТТ: '+', '.join(normal)+'.')
    if unknown_rows:warnings.append(f'Сборщиков без ФИО в детализации: {unknown_rows}. Их заказы сохранены, чтобы итоги совпадали с ТТ.')
    if not groups:warnings.append('За выбранный период ни у одной выбранной ТТ нет дней с общим просроком от 6% включительно.')
    return {'mode':'details','groups':groups,'dates':dates,'period':[dates[0],dates[-1]],'threshold':LIMIT,'thresholdInclusive':True,'badDays':len(bad),'collectorCount':sum(len(d['collectors']) for g in groups for d in g['days']),'collectorSourceRows':source_rows,'unknownCollectors':unknown_rows,'normalCodes':normal,'appeals':0,'orders':sum(g['orders'] for g in groups),'late':sum(g['late'] for g in groups),'warnings':warnings,'canGenerate':bool(groups)}


def detail_rows(group):
    rows=[]
    for day in group['days']:
        rows.append(([dt.date.fromisoformat(day['date']).strftime('%d.%m.%Y')+' · ТТ',n(day['orders']),n(day['late']),pct(day['pct'])],day['pct'],'day'))
        for p in day['collectors']:rows.append(([p['name'] or 'ФИО не указано',n(p['orders']),n(p['late']),pct(p['pct'])],p['pct'],'person'))
    ratio=group['late']/group['orders'] if group['orders'] else None
    rows.append((['Итого за дни с превышением',n(group['orders']),n(group['late']),pct(ratio)],ratio,'total'))
    return rows


def detail_picture(group,dates,path):
    rows=detail_rows(group);width=1500;edges=(0,820,1040,1260,1500);header=190;rh=50
    im=Image.new('RGB',(width,header+rh*len(rows)),'white');draw=ImageDraw.Draw(im)
    draw.text((20,16),group['tt'],font=font(30,True),fill='#243E52')
    draw.text((20,62),f'{dt.date.fromisoformat(dates[0]):%d.%m.%Y} — {dt.date.fromisoformat(dates[-1]):%d.%m.%Y}',font=font(20),fill='#607484')
    draw.text((20,96),f'Детализация сборщиков · просрок ТТ ≥ 6% · дней: {len(group["days"])}',font=font(20),fill='#607484')
    draw.rectangle((0,135,width,header),fill='#'+BLUE)
    for i,label in enumerate(('Дата / Сборщик','Заказы УЗ, шт.','Просрочено, шт.','Общий просрок')):
        draw.text(((edges[i]+edges[i+1])/2,162),label,font=font(20,True),fill='white',anchor='mm')
    for j,(values,ratio,kind) in enumerate(rows):
        y=header+j*rh;bold=kind!='person';fill='#DCE6ED' if bold else ('white' if j%2 else '#F7FAFC')
        draw.rectangle((0,y,width,y+rh),fill=fill)
        draw.rectangle((1260,y,width,y+rh),fill=detail_color(ratio))
        for col,value in enumerate(values):
            face=font(21,bold or col==3)
            if col==0:
                while draw.textlength(value,font=face)>775 and face.size>14:face=font(face.size-1,bold)
                draw.text((20,y+25),value,font=face,fill='#243D50',anchor='lm')
            else:draw.text(((edges[col]+edges[col+1])/2,y+25),value,font=face,fill='#243D50',anchor='mm')
        draw.line((0,y+rh-1,width,y+rh-1),fill='#DCE4EA')
    im.save(path)


def generate_details(data,opts,folder):
    preview=detail_selection(data,opts)
    if not preview['canGenerate']:raise ValueError('Дней с общим просроком ТТ от 6% включительно нет. Детализация не требуется.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);images=folder/'Изображения';images.mkdir(exist_ok=True)
    wb=openpyxl.Workbook();ws=wb.active;ws.title='Детализация сборщиков';ws.sheet_view.showGridLines=False
    ws.column_dimensions['A'].width=70
    for col in 'BCD':ws.column_dimensions[col].width=23
    for group in preview['groups']:
        ws.append([group['tt']]);ws.cell(ws.max_row,1).font=Font(name='Arial',size=15,bold=True,color=BLUE)
        ws.append([f'{dt.date.fromisoformat(preview["dates"][0]):%d.%m.%Y} — {dt.date.fromisoformat(preview["dates"][-1]):%d.%m.%Y} · Только дни с просроком ТТ ≥ 6%'])
        ws.append(['Дата / Сборщик','Заказы УЗ, шт.','Просрочено, шт.','Общий просрок'])
        for c in ws[ws.max_row]:c.fill=PatternFill('solid',fgColor=BLUE);c.font=Font(name='Arial',bold=True,color='FFFFFF')
        refs=[]
        for day in group['days']:
            start=ws.max_row+1;refs.append(start);ws.append([dt.date.fromisoformat(day['date']),day['orders'],day['late'],day['pct']]);ws.cell(start,1).number_format='dd.mm.yyyy'
            for p in day['collectors']:ws.append([p['name'] or 'ФИО не указано',p['orders'],p['late'],p['pct']])
            for c in ws[start]:c.font=Font(name='Arial',bold=True,size=11);c.fill=PatternFill('solid',fgColor='DCE6ED')
        total=ws.max_row+1
        ws.append(['Итого за дни с превышением','=SUM('+','.join(f'B{r}' for r in refs)+')','=SUM('+','.join(f'C{r}' for r in refs)+')',f'=IF(B{total}=0,"",C{total}/B{total})'])
        for c in ws[total]:c.font=Font(name='Arial',bold=True,size=11);c.fill=PatternFill('solid',fgColor='DCE6ED')
        ws.append([]);ws.append([])
        detail_picture(group,preview['dates'],images/(re.sub(r'[<>:"/\\|?*]','_',group['tt'])+'.png'))
    for row in ws:
        ws.row_dimensions[row[0].row].height=27
        for c in row:
            c.alignment=Alignment(vertical='center',horizontal='left' if c.column==1 else 'center')
            if not c.font.name:c.font=Font(name='Arial',size=11)
        c=row[3]
        if isinstance(c.value,(int,float)):
            c.number_format='0.00%';c.fill=PatternFill('solid',fgColor=detail_color(c.value).lstrip('#'))
        elif c.data_type=='f':c.number_format='0.00%'
    wb.save(folder/'Отчёт.xlsx')
    audit={k:v for k,v in preview.items() if k!='groups'}
    audit.update(created=dt.datetime.now().isoformat(timespec='seconds'),stores=len(preview['groups']),dailyRecords=preview['badDays'],appealRecords=0,weeklyPct=preview['late']/preview['orders'] if preview['orders'] else None,sources=data['sources'],details=preview['groups'],checks=['Дни выбраны по общему просроку ТТ от 6% включительно','Суммы сборщиков сверены с ТТ за каждый день','Сборщики без ФИО сохранены в итогах','Один PNG на ТТ, период до семи календарных дней','Итоги относятся только к дням с превышением'])
    (folder/'Проверка.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(folder/'Все результаты.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for p in [folder/'Отчёт.xlsx',folder/'Проверка.json',*sorted(images.glob('*.png'))]:archive.write(p,p.relative_to(folder))
    return audit
