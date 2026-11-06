import json,os,secrets,socket,subprocess as sp,time,urllib.request as u
from pathlib import Path
W=Path('/opt/pd-rehab/releases/mobile-accounts-20261107')
env=os.environ.copy()
env.update(APP_ENV='test',DATABASE_URL='sqlite:///'+str(W/'rehearsal.sqlite'),JWT_SECRET=secrets.token_urlsafe(48),MICRO_EXPRESSION_ENTRY='',EXPERT_LLM_BASE_URL='',TRAINING_VIDEO_ENABLED='false',UPLOAD_DIR=str(W/'staging-uploads'),OUTPUT_DIR=str(W/'staging-outputs'),REPORT_DIR=str(W/'staging-reports'))
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
with (W/'stage-server.log').open('w') as log:
    server=sp.Popen(['/opt/pd-rehab/venv/bin/python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--workers','1','--no-access-log'],cwd=W/'source/backend',env=env,stdout=log,stderr=sp.STDOUT)
    try:
        for _ in range(60):
            assert server.poll() is None,'Staging exited'
            try:
                health=json.load(u.urlopen(f'http://127.0.0.1:{port}/api/system/health',timeout=2))
                if health.get('env')=='test':break
            except (OSError,ValueError):pass
            time.sleep(.5)
        else:raise RuntimeError('Staging health timed out')
        result=sp.check_output(['/opt/pd-rehab/venv/bin/python',str(W/'smoke.py'),f'http://127.0.0.1:{port}/api'],text=True)
        (W/'staging-result.json').write_text(result)
        print(result.strip())
    finally:
        server.terminate()
        try:server.wait(timeout=20)
        except sp.TimeoutExpired:server.kill();server.wait()
