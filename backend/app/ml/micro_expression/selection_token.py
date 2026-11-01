"""Signed, short-lived receipts bind automatic candidates to actual video bytes."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from app.core.config import settings
from app.core.errors import APIError,ErrorCode

VERSION='face-displacement-multiscale-v1'


def _sign(message):
    return hmac.new(settings.jwt_secret.encode(),b'face-selection-v1:'+message,hashlib.sha256).hexdigest()


def issue_selection(candidate,digest,user_id,*,now=None):
    issued=int(time.time() if now is None else now)
    payload=dict(version=VERSION,sha256=digest,user=user_id,
        frames=[candidate[k] for k in ('onset_frame','apex_frame','offset_frame')],expires=issued+1800)
    message=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).rstrip(b'=')
    return message.decode()+'.'+_sign(message)


def verify_selection(token,digest,frames,user_id,*,now=None):
    try:
        if not isinstance(token,str) or len(token)>2048:raise ValueError()
        encoded,signature=token.rsplit('.',1)
        if not hmac.compare_digest(_sign(encoded.encode()),signature):raise ValueError()
        payload=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
        if (payload['version']!=VERSION or payload['sha256']!=digest or payload['frames']!=frames
                or payload['user']!=user_id or payload['expires']<int(time.time() if now is None else now)):
            raise ValueError()
        return dict(source='AUTO_REVIEWED',algorithm_version=VERSION,review_confirmed=True,
            receipt_verified=True,accuracy_validated=False)
    except (ValueError,KeyError,TypeError,UnicodeError) as exc:
        raise APIError(422,ErrorCode.VALIDATION_ERROR,'候选片段已变化或过期，请重新查找并确认，或改用手动选帧。') from exc
