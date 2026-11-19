"""In-memory, descriptive patient reports. No inference or pooled scores."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
import re
import os
import math
from pathlib import Path
from xml.sax.saxutils import escape

SECTIONS = {
    'assessment_sessions': '评估记录', 'finger_tapping_results': '手指敲击结果',
    'micro_expression_results': '已完成面部分析结果', 'functional_assessments': '功能评估',
    'piano_sessions': '钢琴训练', 'pose_sessions': '舞蹈训练',
    'guided_song_sessions': '曲目跟弹', 'training_plans': '训练计划',
    'external_practice_records': '软件端记录',
}
HIDDEN = {'patient_id', 'owner_id', 'operator_id', 'created_by', 'device_id',
          'local_profile_id', 'events', 'events_json', 'raw_events_json'}
LABELS = {'id':'记录编号','completed_at':'完成时间 (UTC)','started_at':'开始时间 (UTC)',
          'created_at':'保存时间 (UTC)','status':'状态','metrics_version':'指标版本',
          'metric_version':'指标版本','input_source':'数据来源','accuracy':'准确率（原始值）',
          'notes':'备注','name':'名称','config_json':'计划配置','result':'保存结果',
          'payload_json':'软件端原始业务数据','algorithm_version':'算法版本'}

TREND_SPECS = {
    'piano_sessions': [('accuracy','准确率','比例 (0-1)'),('timing_mae_ms','节拍绝对误差','ms'),
                       ('mean_response_latency_ms','平均反应延迟','ms')],
    'pose_sessions': [('repetition_count','完成次数','次'),('hold_time_sec','保持时间','秒'),
                      ('valid_pose_frame_ratio','有效姿态帧比例','比例 (0-1)')],
    'finger_tapping_results': [('tapping_frequency','敲击频率','Hz'),('cycle_cv','周期变异系数','无量纲')],
}


def _mapping(value):
    if isinstance(value,str):
        try: value=json.loads(value)
        except (ValueError,TypeError): return {}
    return value if isinstance(value,dict) else {}


def metric_trends(payload):
    """Only known, completed native measurements with stable settings are comparable."""
    groups = {}
    for table, specs in TREND_SPECS.items():
        for row in payload.get('records',{}).get(table,[]):
            if row.get('input_source') != 'HUMAN_KEYBOARD':
                continue  # Demonstrations, self-tests, unlabelled and App schemas stay in detail only.
            audit=_mapping(row.get('difficulty_before_json'))
            if audit.get('completion_status') == 'INTERRUPTED': continue
            at=row.get('completed_at') if table != 'finger_tapping_results' else row.get('created_at')
            if not at: continue
            try:
                stamp=datetime.fromisoformat(str(at).replace('Z','+00:00'))
                stamp=stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
            except (ValueError,TypeError): continue
            if table=='piano_sessions':
                version=row.get('metrics_version')
                task=row.get('recipe_id') or row.get('mode')
                config={key:row.get(key) for key in ('mode','bpm','judgement_window_ms','sequence_length','note_density',
                        'hand_mode','weak_side_ratio','finger_complexity','session_duration_sec','difficulty_engine_version')}
                config.update({key:audit.get(key) for key in ('tempo_ceiling_bpm','weak_hand','recipe_algorithm_version','cue_lead_ms')})
                complete_config=all(row.get(key) is not None for key in ('bpm','judgement_window_ms','sequence_length',
                    'note_density','hand_mode','weak_side_ratio','finger_complexity','session_duration_sec')) and audit.get('cue_lead_ms') is not None
            elif table=='pose_sessions':
                version=row.get('algorithm_version')
                task=row.get('exercise_type')
                config={'execution_mode':row.get('execution_mode'),'exercise_definition_version':row.get('exercise_definition_version'),
                        'difficulty':_mapping(row.get('difficulty_json'))}
                complete_config=all(config.values())
            else:
                version=row.get('analyzer_version')
                task='手指敲击'
                config={key:row.get(key) for key in ('hand','feature_schema_version')}
                complete_config=all(config.values())
            if not version or not task: continue
            # Unknown settings cannot establish compatibility between separate records.
            if not complete_config: config['未完整记录配置_单记录']=row.get('id')
            config_key=json.dumps(config,ensure_ascii=False,sort_keys=True)
            raw=_mapping(row.get('raw_metrics_json')); server=_mapping(audit.get('server_metrics'))
            for key,label,unit in specs:
                value=server.get(key)
                if value is None: value=row.get(key)
                if value is None: value=raw.get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): continue
                identity=(table,str(task),str(version),config_key,key)
                if identity not in groups:
                    groups[identity]={'title':SECTIONS[table],'task':task,'version':version,'source':'HUMAN_KEYBOARD',
                                      'config':config,'metric':key,'label':label,'unit':unit,'points':[]}
                groups[identity]['points'].append({'id':row.get('id'),'at':stamp.isoformat(),'value':value})
    for group in groups.values():
        points=sorted(group['points'],key=lambda p:(p['at'],str(p['id'])))
        values=[p['value'] for p in points]
        group.update(points=points,latest=values[-1],previous=values[-2] if len(values)>1 else None,
                     delta=values[-1]-values[-2] if len(values)>1 else None,minimum=min(values),maximum=max(values))
    return list(groups.values())


def _trend_plot(trend, font):
    """Small vector chart; real UTC spacing, source units, no extrapolation."""
    from reportlab.graphics.shapes import Drawing, Line, PolyLine, Circle, String
    from reportlab.lib import colors
    points=trend['points']; drawing=Drawing(511,120)
    values=[p['value'] for p in points]
    times=[datetime.fromisoformat(p['at']).timestamp() for p in points]
    low,high=min(values),max(values)
    span=high-low
    if span==0: low-=max(abs(low)*0.1,0.1);high+=max(abs(high)*0.1,0.1)
    else: low-=span*0.1;high+=span*0.1
    if trend['unit']=='比例 (0-1)' and min(values)>=0 and max(values)<=1:
        low=max(0,low);high=min(1,high)
    coords=[]
    for stamp,value in zip(times,values):
        x=50+440*(stamp-times[0])/max(times[-1]-times[0],1)
        y=27+70*(value-low)/(high-low)
        coords.extend([x,y])
    drawing.add(Line(50,27,490,27,strokeColor=colors.HexColor('#657080')))
    drawing.add(Line(50,27,50,100,strokeColor=colors.HexColor('#657080')))
    drawing.add(PolyLine(coords,strokeColor=colors.HexColor('#245a98'),strokeWidth=1.3))
    for x,y in zip(coords[::2],coords[1::2]):
        drawing.add(Circle(x,y,2,fillColor=colors.HexColor('#245a98'),strokeColor=None))
    for x,y,text in [(2,94,f'{high:.4g}'),(2,27,f'{low:.4g}'),(50,9,points[0]['at'][:10]),
                     (420,9,points[-1]['at'][:10])]:
        drawing.add(String(x,y,text,fontName=font,fontSize=8))
    return drawing


def _report_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if 'PatientReportCJK' not in pdfmetrics.getRegisteredFontNames():
        candidates = [os.environ.get('PD_REPORT_FONT', ''), '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
                      '/usr/share/fonts/truetype/arphic/uming.ttc', 'C:/Windows/Fonts/simsun.ttc']
        path = next((p for p in candidates if p and Path(p).is_file()), None)
        if not path:
            raise RuntimeError('报告中文字体未配置，请配置 PD_REPORT_FONT 为可嵌入的中文 TrueType 字体。')
        pdfmetrics.registerFont(TTFont('PatientReportCJK', path, subfontIndex=0))
    return 'PatientReportCJK'


def report_sections(payload):
    grouped = defaultdict(list)
    completed = {row['id'] for row in payload.get('records', {}).get('assessment_sessions', []) if row.get('status') == 'COMPLETED'}
    for table, label in SECTIONS.items():
        for row in payload.get('records', {}).get(table, []):
            if table == 'micro_expression_results' and row.get('assessment_session_id') not in completed:
                continue
            config = row.get('config') or row.get('config_json') or {}
            if isinstance(config,str):
                try: config=json.loads(config)
                except (ValueError,TypeError): config={}
            if not isinstance(config,dict): config={}
            result = row.get('result') or {}
            metrics = result.get('metrics') or {} if isinstance(result,dict) else {}
            version = ' / '.join(str(row[k]) for k in (
                'task_version', 'metrics_version', 'metric_version',
                'algorithm_version', 'exercise_definition_version', 'model_version',
                'feature_schema_version', 'analyzer_version') if row.get(k)) or str(metrics.get('metrics_version') or config.get('policy_version') or '未标注版本')
            source = str(row.get('input_source') or row.get('origin') or config.get('input_source') or ('Web / 原生' if table != 'external_practice_records' else '软件端'))
            if row.get('is_simulation'): source='模拟 / 演示数据'
            task = row.get('record_type') or row.get('mode') or row.get('exercise_type') or row.get('song_id') or config.get('song_id')
            grouped[(f'{label} / {task}' if task else label, source, version)].append(row)
    return [{'title': k[0], 'source': k[1], 'version': k[2], 'rows': rows}
            for k, rows in grouped.items()]


def report_filename(payload):
    code = re.sub(r'[^A-Za-z0-9_-]', '_', str(payload['patient'].get('hospital_number') or payload['patient']['id']))[:70]
    dates = payload['date_range']
    period = f"{dates['start_date']}_{dates['end_date']}" if dates.get('start_date') else 'all-history'
    return f'patient-{code}-{period}.pdf'


def render_patient_pdf(payload):
    # Lazy imports keep unrelated services available if deployment misses this dependency.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, KeepTogether
    font = _report_font()
    style = ParagraphStyle('body', fontName=font, fontSize=10, leading=16, wordWrap='CJK')
    heading = ParagraphStyle('heading', parent=style, fontSize=14, leading=22, spaceBefore=14, spaceAfter=8)
    def p(text, fmt=style):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), fmt)
    patient = payload['patient']; dates = payload['date_range']
    now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S UTC+8')
    period = f"{dates['start_date']} 至 {dates['end_date']}（首尾日期均包含）" if dates.get('start_date') else '全部可用历史'
    story = [p('患者随访与训练报告', heading), p(f"患者：{patient.get('name', '')}　编号：{patient.get('hospital_number') or patient['id']}"),
             p(f'日期范围：{period}　时区：Asia/Shanghai (UTC+8)'), p(f'生成时间：{now}'),
             p('本报告汇集已保存的授权记录，仅描述训练和评估数据，不构成医疗诊断或治疗建议。不同来源、任务与指标版本分别呈现，不混合计算分数。'),
             p('记录时间与字段沿用原始保存值；无时区后缀的服务器时间为 UTC。软件端毫秒时间戳为 Unix 时间。字段名保留系统定义，缺失值表示未记录。')]
    sections = report_sections(payload)
    if sections:
        story.append(p('记录概览（仅统计条数，不合并指标分数）', heading))
        for section in sections:
            rows=section['rows']
            completed=sum(bool(r.get('completed_at')) or r.get('status')=='COMPLETED' for r in rows)
            story.append(p(f"{section['title']} / {section['source']} / {section['version']}：{len(rows)} 条，其中标记完成 {completed} 条。"))
    if not sections:
        story.append(p('所选日期范围内暂无可用训练、评估或计划记录。', heading))
    trends=metric_trends(payload)
    story.append(p('客观指标历史趋势', heading))
    story.append(p('以下仅比较明确完成、实际输入且具有指标版本的原生记录。相同任务、来源、版本和已记录配置分别统计，单位保持原定义。缺失值不补零，差值为最新一次减去前一次，不解释为改善或恶化。模拟记录、软件端异构记录与未标注版本仅保留明细。'))
    if not trends:
        story.append(p('当前范围没有满足趋势条件的已保存数值；请查看下方记录明细。'))
    for trend in trends:
        group_start=len(story)
        points=trend['points']
        story.append(p(f"{trend['title']} / {trend['task']} / {trend['label']}（{trend['unit']}）",heading))
        story.append(p(f"来源：{trend['source']}；指标版本：{trend['version']}；配置：{json.dumps(trend['config'],ensure_ascii=False,sort_keys=True)}"))
        story.append(p(f"有效记录 {len(points)} 条；UTC 时间：{points[0]['at']} 至 {points[-1]['at']}。"))
        previous=f"{trend['previous']:.5g}" if trend['previous'] is not None else '无前次记录'
        delta=f"{trend['delta']:+.5g}" if trend['delta'] is not None else '无法比较'
        story.append(p(f"最新值：{trend['latest']:.5g}；前次值：{previous}；差值：{delta}；最小值：{trend['minimum']:.5g}；最大值：{trend['maximum']:.5g}。"))
        if len(points)>1:
            story.append(_trend_plot(trend,font))
        else:
            story.append(p('仅 1 条有效记录，未绘制变化曲线。'))
        group_story=story[group_start:]
        del story[group_start:]
        story.append(KeepTogether(group_story))
    for section in sections:
        story.extend([p(f"{section['title']}（{len(section['rows'])} 条）", heading),
                      p(f"来源：{section['source']}　任务 / 指标版本：{section['version']}")])
        for index, row in enumerate(section['rows'], 1):
            story.extend([Spacer(1, 7), p(f"记录 {index} / {row.get('id', '未标注编号')}")])
            cells = [[p('字段'), p('已保存值')]]
            for key, value in row.items():
                if key in HIDDEN or value is None:
                    continue
                text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
                # Paragraph wraps CJK and long identifiers; splitInRow handles even large JSON cells.
                cells.append([p(LABELS.get(key,key)), p(text)])
            table = LongTable(cells, colWidths=[145, 366], repeatRows=1, splitInRow=1, hAlign='LEFT')
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef2f6')),
                                       ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#d8dee6')), ('LEFTPADDING',(0,0),(-1,-1),6),
                                       ('RIGHTPADDING',(0,0),(-1,-1),6), ('TOPPADDING',(0,0),(-1,-1),4), ('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            story.append(table)
    story.extend([Spacer(1,12),p(f"数据来源：平台数据库授权业务导出。内容校验 SHA-256：{payload.get('integrity', {}).get('sha256', '未提供')}"),
                  p('本报告不包含视频、原始训练事件、聊天内容或账号凭证。详细数据可另行使用授权 JSON / CSV 导出。')])
    output = BytesIO()
    def footer(canvas, doc):
        canvas.setFont(font, 9)
        canvas.drawString(42, 23, '患者随访报告 · 请按机构隐私规范保存')
        canvas.drawRightString(A4[0]-42, 23, f'第 {doc.page} 页')
    SimpleDocTemplate(output,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=42,
                      title='患者随访与训练报告',author='PD-Rehab').build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
