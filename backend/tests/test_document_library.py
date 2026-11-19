import json
from pathlib import Path
import pytest

def test_manifest_permissions_hashes_and_stable_urls():
    from app.services.document_library import library, search
    public=library('PUBLIC')
    assert len(public)>=10
    assert all(x['sha256'] and x['url'].startswith('/pd-rehab/docs/') for x in public)
    assert not any(x['access']!='PUBLIC' for x in public)
    assert len(library('ADMIN'))>len(public)
    assert search('如何注册登录找回密码','PUBLIC')
    assert not any(x['access']!='PUBLIC' for x in search('部署 安装 数据库','PUBLIC'))

def test_allowlist_paths_changes_and_deleted_document(tmp_path):
    from app.services.document_library import DocumentLibrary
    (tmp_path/'ok.md').write_text('# 测试\n同步说明',encoding='utf-8')
    manifest=[{'id':'sync','path':'ok.md','title':'同步','access':'PUBLIC','version':'1','updated_at':'2026-11-19','assets':[]}]
    lib=DocumentLibrary(tmp_path,manifest)
    first=lib.read('sync','PUBLIC')
    (tmp_path/'ok.md').write_text('# 新版本\n训练计划',encoding='utf-8')
    assert lib.read('sync','PUBLIC')['sha256']!=first['sha256']
    assert lib.search('训练计划','PUBLIC')
    (tmp_path/'ok.md').unlink()
    assert not lib.list('PUBLIC')
    manifest[0]['path']='../private.md'
    with pytest.raises(ValueError):DocumentLibrary(tmp_path,manifest)

def test_access_and_arbitrary_assets_denied():
    from app.services.document_library import documents
    with pytest.raises(KeyError):documents.read('../../.env','ADMIN')
    with pytest.raises(PermissionError):documents.read('developer-readme','PUBLIC')
    with pytest.raises(KeyError):documents.asset('piano','../../.env','ADMIN')

def test_public_api_and_private_role(app_client,auth_headers):
    assert app_client.get('/api/documents/piano').status_code==200
    assert app_client.get('/api/documents/developer-readme').status_code==401
    assert app_client.get('/api/documents/developer-readme',headers=auth_headers).status_code==403
    assert app_client.get('/api/documents/no-such-document').status_code==404

def test_ai_citations_are_local_and_permissions_filtered(monkeypatch):
    from app.services import integration_knowledge as k
    monkeypatch.setattr(k.settings,'expert_llm_base_url','')
    result=k.answer_question('如何注册登录找回密码',None,role='PATIENT')
    assert result['sources']
    assert all('/pd-rehab/docs/' in x['url'] for x in result['sources'])
    assert not any('developer-readme' in x['url'] for x in result['sources'])

def test_manifest_reload_revokes_documents_without_process_restart(tmp_path):
    from app.services.document_library import DocumentLibrary
    file=tmp_path/'manifest.json'
    entry=dict(id='guide',path='guide.md',title='指南',access='PUBLIC',version='1',updated_at='2026-11-19',assets=[])
    (tmp_path/'guide.md').write_text('# 指南',encoding='utf-8')
    file.write_text(json.dumps([entry]),encoding='utf-8')
    lib=DocumentLibrary(tmp_path,[entry],manifest_path=file)
    assert lib.read('guide','PUBLIC')
    entry['access']='ADMIN'
    file.write_text(json.dumps([entry]),encoding='utf-8')
    with pytest.raises(PermissionError):lib.read('guide','PUBLIC')
    assert lib.read('guide','ADMIN')['access']=='ADMIN'
    entry['enabled']=False
    file.write_text(json.dumps([entry]),encoding='utf-8')
    assert lib.list('ADMIN')==[]

def test_public_pdf_file_can_be_read_without_exposing_arbitrary_files(tmp_path,monkeypatch,app_client):
    from app.services.document_library import DocumentLibrary
    from app.api import documents as endpoint
    pdf=b'%PDF-1.4\n%%EOF'
    (tmp_path/'guide.pdf').write_bytes(pdf)
    entry=dict(id='guide',path='guide.pdf',title='PDF说明',access='PUBLIC',version='1',updated_at='2026-11-19',assets=[])
    monkeypatch.setattr(endpoint,'documents',DocumentLibrary(tmp_path,[entry]))
    response=app_client.get('/api/documents/guide/file')
    assert response.status_code==200 and response.content==pdf
    assert response.headers['content-type']=='application/pdf'
    assert app_client.get('/api/documents/guide').json()['content'] is None

def test_english_questions_retrieve_authorized_chinese_product_evidence():
    from app.services.document_library import search
    assert any(x['id']=='accounts' for x in search('How do I register and reset my password?','PUBLIC'))
    assert any(x['id']=='reports' for x in search('How can I export a PDF report?','PUBLIC'))
    assert all(x['access']=='PUBLIC' for x in search('download app and synchronize history','PUBLIC'))

def test_document_metadata_never_enters_shared_http_cache(app_client):
    for path in ['/api/documents','/api/documents/piano']:
        response=app_client.get(path)
        assert response.status_code==200
        assert response.headers['cache-control']=='private, no-store'
        assert 'authorization' in {v.strip().lower() for v in response.headers['vary'].split(',')}
