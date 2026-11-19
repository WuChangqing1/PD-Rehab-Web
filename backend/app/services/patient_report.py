"""In-memory, descriptive patient reports. No inference or pooled scores."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
import re
import os
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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
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
