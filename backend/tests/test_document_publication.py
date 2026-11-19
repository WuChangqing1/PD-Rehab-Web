import json,subprocess,sys
from pathlib import Path

def test_republish_preserves_edited_guides_access_revocations_and_extra_documents(tmp_path):
    root=Path(__file__).resolve().parents[2]
    scripts=tmp_path/'scripts';scripts.mkdir()
    script=scripts/'publish_document_inventory.py'
    script.write_bytes((root/'scripts/publish_document_inventory.py').read_bytes())
    library=tmp_path/'docs/library';library.mkdir(parents=True)
    (library/'piano.md').write_text('# 用户已修改的指南',encoding='utf-8')
    (library/'custom.md').write_text('# 新增审核资料',encoding='utf-8')
    entries=[dict(id='piano',path='docs/library/piano.md',title='钢琴',access='ADMIN',enabled=False,version='2',updated_at='2026-11-19',assets=[]),
             dict(id='custom',path='docs/library/custom.md',title='审核',access='PUBLIC',version='1',updated_at='2026-11-19',assets=[])]
    (library/'manifest.json').write_text(json.dumps(entries),encoding='utf-8')
    subprocess.run([sys.executable,str(script)],check=True,capture_output=True)
    assert (library/'piano.md').read_text(encoding='utf-8')=='# 用户已修改的指南'
    result={e['id']:e for e in json.loads((library/'manifest.json').read_text(encoding='utf-8'))}
    assert result['piano']['access']=='ADMIN' and result['piano']['enabled'] is False
    assert result['custom']['sha256']
