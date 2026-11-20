"""Build deterministic documentation manifest; no automatic publication of scanned files."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'docs/library';DIR.mkdir(parents=True,exist_ok=True)
GUIDES={
'accounts':('注册、登录与找回密码','''## App 普通用户
使用 App 的手机号入口获取验证码并按页面完成注册或登录。普通账号关联本人的患者档案；手机号首次登录可能创建账号，不要使用他人的手机号。账号资料中的姓名用于医护端显示，不额外设置昵称。在设置的我的账号与同步查看账号状态。
## Web 工作人员
Web 登录页的医护注册申请用于工作人员申请。申请不会立即授予医护权限，需管理员审核通过。工作人员使用原有用户名密码入口登录。手机号注册与医护注册不是同一入口。
## 找回与故障
App 按找回密码流程验证身份后设置新密码。验证码未收到先检查号码、网络和冷却时间，勿连续请求。Web 工作人员忘记密码请联系管理员，不要重复注册冒充已审核身份。'''),
'piano':('钢琴训练操作与双手练习','''## 开始与操作
进入康复训练的钢琴节奏训练，先在练习目录选择项目，可以浏览和试听。点击开始训练时确认患者，倒计时3、2、1后按高亮琴键对应的字母或触屏琴键。左手与右手以颜色和文字标识，实际手别仍需操作者确认。
## 双手同时敲击
选择双手协调下的双手同时敲击。每拍出现两个高亮键，左右手各负责一个，尽量在同一拍同时按下。结果中的同步误差是两次按下的时间差，不是力度。
## 左右手交替
左右手交替要求每次按该拍提示的一个键，两手轮流响应。不要猜固定字母，以当次屏幕为准。
## 双手错位节奏
按顺序提示先后响应，不要求同时按下。目标错位时差来自当次参数。
## 速度与安全
舒适档降低呈现速度。由医护结合能力选择，不以越快越好为目标。普通键盘和触屏不能可靠测量按压力度，也不自动识别实际手指。'''),
'metrics':('训练与评估指标如何阅读','''## 正确率与完成率
正确率描述符合任务成功条件的比例，完成率描述记录或计划项完成量。两者不同。G2弹奏与等待的主正确率只使用应按项作分母，应等待项另外统计。
## 反应与节拍
反应时间从提示出现算起，节拍误差从目标拍点算起。绝对节拍误差先取绝对值再平均。负误差提前、正误差延后。提示提前量不同的记录不能直接比较反应时间。
## 缺失与比较
暂无数据不是零。只比较任务、难度、速度、辅助、输入方式和指标版本一致的结果。播放完成不代表动作达标。技术指标没有在平台中定义临床正常值或疾病严重度分级。
## 视频结果
手指幅度是归一化距离，不是厘米。膝角来自髋膝踝夹角，直腿接近180度，不能解读成越大弯得越深。面部三分类分数不是帕金森诊断概率。'''),
'sync':('跨端同步、历史与离线重试','''## 保存与同步
App 训练完成后先保存到账号级本地数据库，联网后自动同步。设置中的我的账号与同步显示状态并支持重试。切换账号应使用各自本地数据空间，不混用患者归属。
## Web 查看
工作人员在随访与报告选择有权访问的患者，打开软件端记录查看 App 训练、计划和相关录像。App 的任务指标保留原有口径，不直接当作 Web 钢琴指标混合绘图。
## 未同步的排查
确认已登录、绑定患者正确、网络可用、记录确已完成保存。离线、授权过期、账号失效或上传失败可影响同步。保留失败提示并重试，不要为重试重复做一条相同记录。删除和跨端变化以受控同步协议为准。'''),
'face':('面部录像、选帧与结果','''## 录制与上传
在评估中心进入面部表现分析，确认患者后打开摄像头，开始录制，停止后继续选帧和分析；也可以选择已有视频。单人正脸、光照均匀、头部稳定，建议8到15秒包含一次完整表情变化。无需额外点击开始检查。
## 候选片段
自动选帧给出开始、变化最明显和结束的候选位置；按页面确认。没有清楚候选可能是遮挡、头动、缺少边界或变化不足，不表示没有症状。
## 分析结果
模型就绪且分析成功后显示负向、正向、惊讶三类分数和主导标签。它们是模型分类输出，不是疾病风险、真实情绪证明或临床严重度。低帧率录像可能与训练数据条件不同。
## App 训练录像
App 视频先加密保存并按授权分块上传。工作人员可查看录像、分段复核和分析结果；失败、取消或无有效片段不是患者零分。删除和保存期限遵循原有授权，不恢复已删除视频。'''),
'dance':('舞蹈课程与芭蕾动作','''## 视频课程
康复训练提供舞蹈视频课程与芭蕾动作训练。舞蹈课程包含新平衡舞步六式、Brain and Body、Move and Shout；以目录实际分段为准，按页播放。
## 动作训练
按医护指导选择坐姿或站姿扶椅，确保支撑稳固和身体入镜。选择动作、确认患者后按提示完成并查看视频分析结果。动作不适合或出现不适时停止并告知医护。
## 结果边界
App 视频课程记录播放时长、覆盖与已播完部分，不能证明患者完成动作。Web 姿态分析提供角度、检测次数、保持时间与输入质量，单目角度不是标定三维测量。'''),
'plans':('训练计划与每日进度','''## 计划与进度
在已有计划页面查看安排的训练、日期、次数或时长目标。完成并保存符合条件的训练后，系统按当天、账号、项目和计划匹配累计daily_progress。
## 统计方法
次数型按符合条件的保存记录计数；舞蹈分钟型按播放观察时长累计。达标表示保存量达到计划目标，不等于医学依从性评分。单次训练可能同时匹配多个计划，不要把各计划进度相加当作唯一训练总量。
## 不更新时
检查是否保存完成、当天安排是否有效、账号及患者是否一致、训练项目是否匹配、同步是否成功。暂停或过期计划不按同一规则计入当前安排。'''),
'reports':('随访报告与数据导出','''## 选择患者
随访与报告先选择当前账号有权访问的患者。未选择患者不能导出全部人的资料。
## PDF 报告
使用导出PDF报告按钮，在弹窗选择开始和结束日期，可用最近7天、最近30天、本月或全部历史。范围包含首尾两天，按UTC+8统计。取消不生成报告。
## 报告内容
报告保留实际存在的患者资料、训练和评估、App原始任务结果、计划及已完成面部结果。不同任务、参数或指标版本不混合计算。空范围明确显示无数据；不自动给出诊断和治疗结论。
## 业务导出
有权限的工作人员可在同一导出区域下载JSON或CSV，包含结构化记录及受控附件元数据。导出不包含密码、令牌或密钥，也不恢复已删除录像。妥善保存下载的患者资料。'''),
'assistant':('AI 问答与资料引用','''## 如何提问
可以询问注册登录、钢琴与舞蹈训练、录像分析、同步、指标和导出操作。输入问题按Enter发送，Shift+Enter换行，中文输入法选词时回车不会误发送。
## 来源阅读
回答引用链接进入本站文档阅读页面。资料按权限检索，公众使用资料、工作人员和内部技术资料分开。没有相应证据时应明确说明，不凭空猜测功能。
## 隐私与限制
AI问答不读取患者个人病历，不代替诊断、处方或药物调整。平台保留问答会话记录，模型供应商处理的是问题及获授权的文档片段，患者数据库不混入公共知识库。'''),
'faq':('常见问题与故障排查','''## 登录与验证码
检查网络、账号入口、手机号及验证码有效期。医护申请待审核时不能立即登录工作人员系统。验证码有冷却和限流，反复请求不会加快送达。错误持续时向管理员提供时间和错误提示，不发送密码和验证码。
## 训练与声音
先点击试听或开始使浏览器允许音频，检查设备静音和音量。使用屏幕显示的字母、颜色和手别提示。不要把网络同步放在操作计时流程里手动反复重启。
## 摄像头与上传
在线摄像头需要HTTPS和浏览器权限。确认摄像头没有被其他应用占用。录像先停止保存再分析；上传失败查看状态并重试，勿删除仍待上传的原始记录。
## 结果为空
区分没有记录、输入质量不合格、模型未就绪、无有效片段和样本不足。空值不是零，不用重复录入虚构分数来填充趋势。'''),
}
previous=json.loads((DIR/'manifest.json').read_text(encoding='utf-8')) if (DIR/'manifest.json').exists() else []
manifest=[]
for key,(title,body) in GUIDES.items():
    p=DIR/(key+'.md')
    if not p.exists():p.write_text('# '+title+'\n\n'+body.strip()+'\n',encoding='utf-8')
    manifest.append(dict(id=key,path=p.relative_to(ROOT).as_posix(),title=title,access='PUBLIC',version='2026-11-19',updated_at='2026-11-19',assets=[]))
for key,path,title,access in [
 ('developer-readme','README.md','项目 README 与运行说明','ADMIN'),
 ('metric-reference','docs/metric_definitions.md','Web 指标技术定义','STAFF'),
 ('integration-authority','docs/INTEGRATION_ENTITY_AUTHORITY.md','双端数据权威与一致性','ADMIN'),
 ('staff-guide','docs/staff-accounts-20261118/使用与验收.md','工作人员权限与使用','STAFF')]:
    if (ROOT/path).is_file():
        assets=[]
        if key=='developer-readme':
            text=(ROOT/path).read_text(encoding='utf-8')
            text=re.sub(r'<img\s+src="([^"]+)"\s+alt="([^"]*)"[^>]*>',lambda m:'!['+m[2]+']('+m[1]+')',text)
            def image(m):
                asset=m[2]
                if not asset.startswith('docs/') or '..' in asset or not (ROOT/asset).is_file():return m[1]
                assets.append(asset)
                return '!['+m[1]+'](../../'+asset+')'
            text=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',image,text)
            # Relative links retain original README root semantics after publication.
            text=re.sub(r'(?<!!)\[([^\]]+)\]\((?!https?:|#|mailto:)([^)]+)\)',lambda m:'['+m[1]+'](../../'+m[2]+')',text)
            path='docs/library/developer-readme.md';(ROOT/path).write_text(text,encoding='utf-8')
        manifest.append(dict(id=key,path=path,title=title,access=access,version='source-4794609',updated_at='2026-11-19',assets=assets))
prior={e['id']:e for e in previous}
for entry in manifest:
    if entry['id'] in prior:
        for key in ('access','enabled','product_version','status'):
            if key in prior[entry['id']]:entry[key]=prior[entry['id']][key]
    entry['sha256']=hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()
generated={e['id'] for e in manifest}
manifest.extend(e for e in previous if e['id'] not in generated and (ROOT/e['path']).is_file())
for entry in manifest:entry['sha256']=hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()
(DIR/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
approved={e['path']:e for e in manifest}
old_inventory=json.loads((DIR/'inventory.json').read_text(encoding='utf-8')) if (DIR/'inventory.json').exists() else []
inventory=[e for e in old_inventory if e.get('repository')=='App']
for p in sorted(ROOT.rglob('*')):
    if p.suffix.lower() not in ('.md','.pdf') or any(x in p.relative_to(ROOT).parts for x in ('.git','node_modules','data','_deploy','output','private','.test-temp','.pytest_cache','.dart_tool','tmp','validation','build','uploads','outputs')):continue
    path=p.relative_to(ROOT).as_posix();entry=approved.get(path)
    inventory.append({'repository':'Web','path':path,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'published_id':entry['id'] if entry else None,'decision':'explicitly-approved' if entry else 'excluded-unreviewed-historical-or-internal'})
(DIR/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'published':len(manifest),'review_inventory':len(inventory),'formats':{'markdown':len(manifest),'pdf':0}}))
