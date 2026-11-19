import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def percent(x):return f'{100*x:.1f}%'
def main():
    summary=read('analysis/summary.json')
    audit=read('analysis/audit.json')
    reviews=read('analysis/case_reviews.json')
    pdfmetrics.registerFont(TTFont('Arial','C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('ArialBold','C:/Windows/Fonts/arialbd.ttf'))
    normal=ParagraphStyle('body',fontName='Arial',fontSize=9,leading=12,spaceAfter=6)
    small=ParagraphStyle('small',parent=normal,fontSize=7.5,leading=9.5,spaceAfter=4)
    heading=ParagraphStyle('heading',parent=normal,fontName='ArialBold',fontSize=12,leading=16,spaceBefore=7)
    title=ParagraphStyle('title',parent=heading,fontSize=19,leading=24,spaceAfter=10)
    story=[]
    def p(value,style=normal):story.append(Paragraph(escape(str(value)),style))
    def short(value,n=300):
        value=str(value).replace(chr(10),' ')
        return value if len(value)<=n else value[:n]+'…'
    def table(rows,widths):
        item=Table([[Paragraph(escape(str(value)),small) for value in row] for row in rows],colWidths=widths)
        item.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#e2edf8')),('VALIGN',(0,0),(-1,-1),'TOP'),
                                 ('LINEBELOW',(0,0),(-1,-1),.25,HexColor('#c9d5e2')),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.extend([item,Spacer(1,6)])
    p('ЛР5. Надёжность агента',title)
    p('ReAct ЛР4, AgentDojo 0.1.35, workspace и banking v1.2.2. Системный промпт и базовый цикл ЛР4 сохранены по SHA-256. Qwen3-4B-Instruct-2507 Q4_K_M, llama.cpp b12110, RTX 3060 12 ГБ. Контекст 16384, до 15 вызовов модели и 15 попыток инструментов, выход до 1024 токенов. 316 основных и 20 отладочных эпизодов.')
    p('Прогноз до измерений',heading)
    p('При T=0 ожидаю 0–10% задач с разной успешностью. При T=0,7 — 20–40% нестабильных задач и падение pass^5 относительно pass^1 на 10–25 п.п. P1 может дублировать запись после тайм-аута, P2 ожидается безопаснее. Успешность banking ожидается ниже на 5–20 п.п. Прогноз и параметры зафиксированы до запусков.',small)
    p('1. Повторные прогоны',heading)
    st=summary['stability']
    p(f"T=0: успешных {st['t0_successes'][0]}/30 и {st['t0_successes'][1]}/30. Разный вердикт у {len(st['different_tasks_t0'])}/30 задач. T=0,7, пять разных seed: нестабильных {len(st['unstable_tasks'])}/30 ({percent(st['unstable_fraction'])}).",small)
    p('pass^k = C(c,k)/C(n,k) — все k запусков успешны. pass@k = 1 − C(n−c,k)/C(n,k) — хотя бы один. Считаются по каждой задаче, затем усредняются. Для 3 успехов из 5: pass^1=0,6, pass^2=0,3, pass^3=0,1, pass@2=0,9.',small)
    story.append(Image('analysis/stability.png',width=500,height=154))
    p('Точки рассчитаны по пяти сохранённым эпизодам каждой задачи; выбор лучшего запуска не применяется.',small)
    difference=st['t0_first_difference']
    if difference:
        a=difference['first'];b=difference['second']
        p(f"Первое различие T=0: {difference['traces']}, событие {difference['event_number']}.",small)
        p('Первый прогон: '+short(a.get('response',a),240),small)
        p('Второй прогон: '+short(b.get('response',b),240),small)
        p('Seed одинаков. Возможная причина — численные различия GPU и состояние кеша. Конкретный источник отдельным опытом не изолировался.',small)
    else:
        p('При T=0 расхождения успешности не обнаружены: 14/30 в обоих прогонах. Однако полные трейсы не идентичны: '+reviews['t0_trace_explanation'],small)
    if st.get('unstable_example'):
        example=st['unstable_example']
        p('Затраты разных исходов одной задачи '+example['task'],heading)
        rows=[['Прогон / seed','Успех','Вызовы модели / инструментов','Вход / выход токенов','Время, с']]
        for r in example['runs']:
            rows.append([f"{r['run']+1} / {r['seed']}",r['utility'],f"{r['model_calls']} / {r['tool_calls']}",
                         f"{r['input_tokens']} / {r['output_tokens']}",f"{r['seconds']:.1f}"])
        table(rows,[83,42,143,143,89])
        p(reviews['unstable_explanation'],small)
    story.append(PageBreak())
    p('2. Сбои и повторы',title)
    p('fault_p=0,2. Ошибка A возникает до исполнения; B — потеря ответа после успешного действия записи. В конфигурации 11 инструментов workspace помечены как меняющие состояние, включая get_unread_emails. P0 передаёт ошибку модели; P1 делает до двух автоматических повторов любого ошибочного вызова; P2 повторяет чтение, а для записи предупреждает о возможном выполнении.',small)
    rows=[['Вариант','Успех /30','Сбоев A/B','Лишние вызовы модели / инструментов','Дубли записей','Потеряны / получены']]
    base=summary['transfer']['workspace']
    rows.append(['Без сбоев',f"{base['successes']}/30",'0 / 0','0 / 0',reviews['baseline_duplicates'],'—'])
    for policy,v in summary['faults'].items():
        rows.append([policy,f"{v['successes']}/30 ({percent(v['successes']/30)})",f"{v['fault_types'].get('A',0)} / {v['fault_types'].get('B',0)}",
                     f"{v['extra_model_calls']:+d} / {v['extra_tool_calls']:+d}",v['duplicate_writes'],f"{len(v['lost'])} / {len(v['gained'])}"])
    table(rows,[62,90,67,135,64,82])
    p('Лишние вызовы — разность суммарных затрат с первым T=0 прогоном, поэтому значение может быть отрицательным. Дубль — повторное успешное исполнение инструмента записи с идентичными аргументами. Это включает идемпотентные операции. Для вреда важен тип действия.',small)
    p('Сопоставимость сбоев',heading)
    p('Для каждой попытки номер увеличивается. Seed выводится через SHA-256 строки «набор:задача:seed:номер попытки». Во всех политиках seed=42. При одинаковой траектории совпадают случайные числа и сбои. После автоматического повтора номера смещаются относительно P0; последующие действия и сбои могут расходиться. Это ограничение сравнения учитывается.',small)
    for case,title_text in [('duplicate_P1','Повторное выполнение P1'),('recovered_P0','Восстановление P0 средствами модели')]:
        p(title_text,heading)
        r=summary['cases'][case]
        if r is None:
            p('Такой случай в основной серии отсутствует. Контрольный тест B подтверждает две отправки P1 и одну P2.',small)
            continue
        p(f"{r['key']}, utility={r['utility']}. "+reviews[case]['explanation'],small)
        p(reviews[case]['journal_excerpt'],small)
        p('Ответ после ошибки: '+short(reviews[case]['model_response'],450),small)
        p('Трейс: '+r['trace'],small)
    p(reviews['p2_limitation'],small)
    p('Проверки без модели',heading)
    p('При единичном гарантированном сбое A и восстановлении сервиса P2 получает чтение со второй попытки. Постоянный fault_p=1 даёт три ошибки подряд и остановку повторов. После потерянного ответа send_email P1 отправил два письма, P2 одно. При fault_p=0 сценарий повторил 36/40 ЛР4.',small)
    p('Серверная защита от дубля потребовала бы idempotency key: одинаковый ключ возвращает сохранённый результат без второго выполнения. Инструменты AgentDojo такого ключа не имеют.',small)
    story.append(PageBreak())
    p('3. Перенос на banking',title)
    rows=[['Набор','Успех','Доля','95% Уилсон']]
    for name,v in summary['transfer'].items():
        rows.append([name,f"{v['successes']} из {v['n']}",percent(v['rate']),f"{percent(v['wilson'][0])}–{percent(v['wilson'][1])}"])
    table(rows,[120,110,100,170])
    p('Workspace — первый прогон T=0; banking — один прогон на всех 16 задачах. Промпт и обвязка не менялись после просмотра банковских результатов. Интервалы оценивают масштаб неопределённости при допущении независимых задач; пересечение само по себе не устанавливает равенство качества.',small)
    story.append(Image('analysis/faults_transfer.png',width=500,height=205))
    for case in reviews['banking_failures']:
        p(case['task']+'. '+case['prompt'],heading)
        p('Ответ: '+short(case['answer'],350),small)
        p('Наблюдение: '+short(case['observation'],350),small)
        p(case['explanation'],small)
        p('Трейс: '+case['trace'],small)
    p('4. Повышение частоты сбоев на dev',heading)
    p('Прогноз до запуска: P2 при 0,5 потеряет 1–3 задачи из 10, количество попыток возрастёт. Проверены одни и те же 10 отладочных задач с seed=42.',small)
    rows=[['fault_p','Успех /10','Модель, вызовы','Инструменты, попытки','Сбои']]
    for probability,v in summary['question7'].items():
        rows.append([probability,v['successes'],v['model_calls'],v['tool_calls'],v['faults']])
    table(rows,[75,90,110,140,85])
    story.append(PageBreak())
    p('5. Содержательная проверка ответов',title)
    p('По порядку записей выбраны 10 засчитанных и 5 незасчитанных эпизодов из workspace и banking. Проверены действие, данные и явно заданный формат ответа; при необходимости сверены инструменты и изменения среды. Содержательный разбор выполнен с помощью Codex и сохранён отдельно в analysis/audit.json.',small)
    rows=[['Набор / задача','Utility','По смыслу','Основание']]
    for r in audit:
        rows.append([r['suite']+'/'+r['task'].removeprefix('user_task_'),str(r['benchmark']),str(r['semantic_success']),r['reason']])
    table(rows,[90,48,60,302])
    mismatch=[r for r in audit if r['benchmark']!=r['semantic_success']]
    p(f"Расхождений {len(mismatch)}/15. Выборка целевая, малая и не является оценкой частоты ошибок судьи во всём наборе.",small)
    for r in sorted(mismatch,key=lambda r:r['suite']!='banking')[:2]:
        p(r['suite']+'/'+r['task']+': '+short(r['answer'],450),small)
        p('Почему оценка расходится: '+r['reason'],small)
    p('В banking/6 проверка выбирает первую запись с iphone/spotify/subscription, включая старый Spotify=50. Исправление: проверять новую запись относительно исходного состояния, получателя, сумму 50 и recurring=True. В banking/8 utility всегда True: нужна проверка категорий, сумм и направлений платежей. Код проверок сохранён в analysis/checker_evidence.json.',small)
    p('Выводы о надёжности',heading)
    p(reviews['conclusion'],small)
    p('Все 336 эпизодов учитываются, ошибки инфраструктуры остаются в знаменателе. Ключ включает набор, задачу, конфигурацию, номер прогона и seed; пропускаются только записанные ключи. Трейсы содержат вызовы, результаты, ошибки и журнал сбоев. Кодогенерация — Codex. Материалы: frozen.json, manifest.json, results.jsonl, analysis и traces.',small)
    p('Источники: задание ЛР5; AgentDojo v1.2.2; τ-bench (pass^k); Chen et al. 2021 (pass@k); NIST (интервал Уилсона).',small)
    def footer(c,d):
        c.setFont('Arial',8);c.drawString(45,23,'ЛР5 · AgentDojo · воспроизводимая оценка');c.drawRightString(550,23,str(d.page))
    SimpleDocTemplate('report.pdf',pagesize=(595.28,841.89),leftMargin=45,rightMargin=45,topMargin=35,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer)
    import pypdfium2
    document=pypdfium2.PdfDocument('report.pdf')
    assert 3<=len(document)<=4,len(document)
    Path('analysis/preview').mkdir(exist_ok=True)
    for i,page in enumerate(document,1):page.render(scale=1.3).to_pil().save(f'analysis/preview/{i}.png')
    print('Report:',len(document),'pages')

if __name__=='__main__':main()
