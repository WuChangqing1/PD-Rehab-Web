"""Curated, source-backed snippets; no patient record retrieval or arbitrary SQL.

Reviewed against current product source and cited primary guidance on 2026-11-03.
Retrieval is lexical, not a claimed semantic/clinical RAG evaluation.
"""
import re
from app.core.config import settings
from app.core.errors import APIError,ErrorCode
WEB='https://github.com/WuChangqing1/PD-Rehab-Web/blob/main/'
ENTRIES=[
 {'id':'face','terms':['面部','表情','录像','录制','摄像头','关键帧','face','camera'],
  'text':'进入评估中心的面部表现分析，选择患者，打开摄像头后开始录制，结束后确认候选的开始、变化最明显、结束三个画面，再开始分析。建议录制8到15秒，保持单人正脸和头部稳定。也可以上传已有录像。三类分数是负向、正向、惊讶，不是疾病诊断。',
  'title':'平台面部分析使用说明','url':WEB+'docs/auto-face-keyframes.md'},
 {'id':'piano','terms':['钢琴','节奏','左右手','按键','琴键','piano'],
  'text':'在康复训练中选择钢琴练习，可以先浏览和试听。点击开始时确认患者，等待3秒倒计时，再按高亮琴键对应的字母或触屏提示练习。普通键盘和触屏不能可靠测量按压力度。',
  'title':'平台训练操作说明','url':WEB+'运行与使用说明.md'},
 {'id':'sync','terms':['同步','绑定','软件','记录','历史','离线','sync'],
  'text':'软件端使用与Web相同的账号和HTTPS API，选择并绑定患者后手动同步。原始训练记录不可变，断网后可重试；同ID不同内容会报冲突。Web原生记录是只读快照，不与软件原始指标直接混合统计。',
  'title':'跨端集成协议说明','url':WEB+'docs/CROSS_CLIENT_INTEGRATION_HANDOFF.md'},
 {'id':'exercise','terms':['康复','锻炼','运动','舞蹈','芭蕾','exercise'],
  'text':'帕金森病康复中的运动计划应结合个人能力，并由医疗团队协助制定；运动与物理治疗可支持活动、平衡和日常功能，不能替代药物或专业治疗。具体训练强度与是否适合站姿练习，请咨询自己的医生或治疗师。',
  'title':"Parkinson’s Foundation：Exercise",'url':'https://www.parkinson.org/living-with-parkinsons/treatment/exercise'},
]
SAFETY={'title':'NHS：Parkinson’s disease treatment','url':'https://www.nhs.uk/conditions/parkinsons-disease/treatment/'}

def answer_question(question,provider):
    if not question.strip():raise APIError(422,ErrorCode.VALIDATION_ERROR,'请输入问题。')
    high=any(term in question for term in ['加药','停药','减药','剂量','开药','处方','诊断','是不是帕金森','胸痛','呼吸困难','昏倒','自杀'])
    if high:
        return dict(answer='无法根据聊天或训练分数进行诊断或调整药物。请联系你的医生；若出现胸痛、明显呼吸困难、意识改变等紧急症状，应立即寻求当地急救。',model='safety-policy-v1',sources=[SAFETY],provider_used=False,safety_limited=True)
    ranked=sorted(((sum(term.lower() in question.lower() for term in e['terms']),e) for e in ENTRIES),key=lambda pair:pair[0],reverse=True)
    matched=[entry for score,entry in ranked[:2] if score>0]
    sources=[{'title':e['title'],'url':e['url']} for e in matched]
    if settings.expert_llm_base_url and settings.expert_llm_model:
        # Bound context only; source links are fixed by retrieval, never fabricated by the model.
        context='\n'.join(e['text'] for e in matched)
        prompt='仅根据以下已审核资料回答平台或一般康复知识问题，资料不足时明确说明。不得诊断、开药、编造来源或声称读取个人病历。\n资料：'+context+'\n问题：'+question
        answer=provider(prompt)
        return dict(answer=answer,model=settings.expert_llm_model,sources=sources,provider_used=True,safety_limited=False)
    if matched:
        return dict(answer='\n\n'.join(e['text'] for e in matched),model='platform-knowledge-v1',sources=sources,provider_used=False,safety_limited=False)
    raise APIError(503,ErrorCode.MODEL_NOT_CONFIGURED,'此问题超出平台知识范围，且大模型服务未配置。')
