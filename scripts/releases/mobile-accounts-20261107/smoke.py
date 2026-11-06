import json,secrets,sys,urllib.request as u,urllib.error as e
base=sys.argv[1].rstrip('/')
assert base.startswith('http://127.0.0.1:') or base.startswith('https://127.0.0.1:'),'Isolated loopback only'
def req(method,path,data=None,token=None,expected=200):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=u.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    try:
        with u.urlopen(request,timeout=30) as r:
            status=r.status;body=json.load(r)
    except e.HTTPError as err:status=err.code;body=json.load(err)
    assert status in (expected if isinstance(expected,tuple) else (expected,)),(method,path,status,expected)
    return body
pw=secrets.token_urlsafe(20);prefix='qa_'+secrets.token_hex(6)
a=req('POST','/mobile/auth/register',{'username':prefix,'password':pw,'display_name':'Release QA','sync_consent_version':'account-sync-v1'},expected=201)
b=req('POST','/mobile/auth/register',{'username':prefix+'_b','password':pw,'display_name':'Isolated QA','sync_consent_version':'account-sync-v1'},expected=201)
assert a['patient']['id']!=b['patient']['id'] and a['patient']['hospital_number']!=b['patient']['hospital_number']
req('GET','/patients',token=a['access_token'],expected=403)
bootstrap=req('GET','/integration/v1/bootstrap',token=a['access_token'])
assert bootstrap['staff']==[] and [p['id'] for p in bootstrap['patients']]==[a['patient']['id']]
identity={'device_id':prefix+'-device','local_profile_id':prefix+'-profile','patient_id':a['patient']['id']}
link=req('POST','/integration/v1/bindings',identity,token=a['access_token'])
req('POST','/integration/v1/bindings',identity,token=b['access_token'],expected=403)
payload=dict(identity,source_record_id='release-smoke',record_type='OTHER',schema_version='flutter-v4',payload={'release_check':True})
first=req('POST','/integration/v1/records',payload,token=a['access_token'],expected=201)
again=req('POST','/integration/v1/records',payload,token=a['access_token'],expected=201)
assert first['id']==again['id'] and again['already_synced']
req('GET','/integration/v1/records/'+first['id']+'?patient_id='+a['patient']['id'],token=b['access_token'],expected=(403,404))
rotated=req('POST','/mobile/auth/refresh',{'refresh_token':a['refresh_token']})
req('POST','/mobile/auth/refresh',{'refresh_token':a['refresh_token']},expected=401)
req('POST','/mobile/auth/logout',{'refresh_token':rotated['refresh_token']})
req('GET','/mobile/auth/me',token=rotated['access_token'],expected=401)
req('POST','/mobile/auth/logout',{'refresh_token':b['refresh_token']})
print(json.dumps({'registration':True,'unique_patient_numbers':True,'self_only_bootstrap':True,'cross_patient_denied':True,'record_idempotent':True,'refresh_rotated':True,'logout_revoked':True,'isolated_database_only':True}))
