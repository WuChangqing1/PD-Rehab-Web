"""Real provider preflight with synthetic speech; no production records accessed."""
import asyncio,json,uuid,wave
from pathlib import Path
from app.core.config import settings
from app.services.asr_stream import available,open_provider,command,Transcript
from app.api.integration import _ask_llm

async def main():
    assert available()
    with wave.open(str(Path(__file__).with_name('mandarin.wav')),'rb') as audio:
        assert audio.getframerate()==16000 and audio.getnchannels()==1 and audio.getsampwidth()==2
        pcm=audio.readframes(7*16000)
    transcript=Transcript()
    async with open_provider() as provider:
        task=str(uuid.uuid4());await provider.send(command('run-task',task))
        started=json.loads(await asyncio.wait_for(provider.recv(),10))
        assert started.get('header',{}).get('event')=='task-started'
        async def upload():
            for i in range(0,len(pcm),3200):
                await provider.send(pcm[i:i+3200]);await asyncio.sleep(.1)
            await provider.send(command('finish-task',task))
        sender=asyncio.create_task(upload())
        try:
            async with asyncio.timeout(30):
                while True:
                    event=json.loads(await provider.recv());kind=event.get('header',{}).get('event')
                    if kind=='result-generated':transcript.apply(event['payload']['output']['sentence'])
                    elif kind=='task-finished':break
                    elif kind=='task-failed':raise RuntimeError('ASR provider rejected test; details withheld')
            await sender
        finally:
            sender.cancel();await asyncio.gather(sender,return_exceptions=True)
    assert '左右手交替训练' in transcript.text(), 'Synthetic speech mismatch'
    answer=await asyncio.to_thread(_ask_llm,'你是平台操作助手。本次是无患者数据的发布自测。只回答操作知识。','请用一句话提示使用者：语音转文字后先检查文字，再点击发送。')
    assert answer.strip()
    print(json.dumps({'asrRealProvider':True,'syntheticMandarinMatched':True,'glmModel':settings.expert_llm_model,'glmAnswerCharacters':len(answer),'patientRecordsAccessed':False}))

asyncio.run(main())
