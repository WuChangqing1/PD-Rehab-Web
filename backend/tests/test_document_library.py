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
