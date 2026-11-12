"""Real provider adapters. No demo passwords, fixed OTPs, or client identity trust."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
import json
import re
import urllib.parse
import urllib.request
from app.core.config import settings
from app.core.errors import APIError


def unavailable():
    return APIError(503, 'LOGIN_PROVIDER_UNAVAILABLE', '此登录方式暂不可用，请使用账号密码登录。')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LoginProviders:
    @property
    def wechat_enabled(self):
        return bool(settings.mobile_wechat_enabled and settings.mobile_wechat_app_id
                    and settings.mobile_wechat_app_secret)

    @property
    def sms_enabled(self):
        return bool(settings.mobile_sms_enabled and settings.mobile_sms_access_key_id
                    and settings.mobile_sms_access_key_secret and settings.mobile_sms_sign_name
                    and settings.mobile_sms_template_code)

    @property
    def wechat_app_id(self):
        return settings.mobile_wechat_app_id

    def wechat_subject(self, code):
        if not self.wechat_enabled:
            raise unavailable()
        # Fixed HTTPS endpoint; never log URL/exceptions containing code/secret.
        url = 'https://api.weixin.qq.com/sns/oauth2/access_token?' + urllib.parse.urlencode({
            'appid': self.wechat_app_id, 'secret': settings.mobile_wechat_app_secret,
            'code': code, 'grant_type': 'authorization_code'})
        try:
            opener = urllib.request.build_opener(_NoRedirect())
            with opener.open(url, timeout=8) as response:
                body = json.loads(response.read(65536))
        except Exception:
            raise unavailable() from None
        if not isinstance(body, dict):
            raise unavailable()
        subject = body.get('openid')
        if (body.get('errcode', 0) != 0 or not isinstance(body.get('access_token'), str)
                or not body['access_token'] or not isinstance(subject, str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', subject)):
            raise APIError(401, 'WECHAT_AUTH_FAILED', '微信授权已失效，请重新授权。')
        # OpenID is scoped by configured AppID. Never merge patients by nickname,
        # avatar or an unverified client-supplied UnionID/phone number.
        return subject

    @staticmethod
    def rpc_signature(parameters, secret):
        # Aliyun RPC Signature v1.0 (RFC 3986), compatible with its official SDK.
        encode = lambda value: urllib.parse.quote(str(value), safe='-_.~')
        canonical = '&'.join(encode(k)+'='+encode(v) for k, v in sorted(parameters.items()))
        signing = 'POST&%2F&'+encode(canonical)
        return base64.b64encode(hmac.new((secret+'&').encode(), signing.encode(), hashlib.sha1).digest()).decode()

    def _sms_rpc(self, action, parameters):
        if not self.sms_enabled:
            raise unavailable()
        values = {k: str(v) for k, v in parameters.items() if v is not None}
        values.update(Action=action, Version='2017-05-25', Format='JSON',
            AccessKeyId=settings.mobile_sms_access_key_id, SignatureMethod='HMAC-SHA1',
            SignatureVersion='1.0', SignatureNonce=secrets.token_urlsafe(24),
            Timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        values['Signature'] = self.rpc_signature(values, settings.mobile_sms_access_key_secret)
        # POST body rather than a URL containing phone/code. No redirects,
        # automatic retries, request/response logs, or returned verification codes.
        request = urllib.request.Request('https://dypnsapi.aliyuncs.com/',
            data=urllib.parse.urlencode(values).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=8) as response:
                body = json.loads(response.read(65536))
        except Exception:
            raise unavailable() from None
        if not isinstance(body, dict) or body.get('Code') != 'OK' or body.get('Success') is not True:
            raise unavailable()
        return body

    def send_sms(self, phone, challenge_id):
        self._sms_rpc('SendSmsVerifyCode', {
            'SchemeName': settings.mobile_sms_scheme_name or None,
            'CountryCode': '86', 'PhoneNumber': phone,
            'SignName': settings.mobile_sms_sign_name, 'TemplateCode': settings.mobile_sms_template_code,
            'TemplateParam': json.dumps({'code': '##code##', 'min': '5'}),
            'CodeType': '1', 'CodeLength': '6', 'ValidTime': '300',
            'DuplicatePolicy': '1', 'Interval': '60', 'AutoRetry': '0',
            'OutId': challenge_id, 'ReturnVerifyCode': 'false'})

    def verify_sms(self, phone, code, challenge_id):
        body = self._sms_rpc('CheckSmsVerifyCode', {
            'SchemeName': settings.mobile_sms_scheme_name or None,
            'CountryCode': '86', 'PhoneNumber': phone, 'VerifyCode': code, 'OutId': challenge_id})
        model = body.get('Model')
        return isinstance(model, dict) and model.get('VerifyResult') == 'PASS'


def get_login_providers():
    return LoginProviders()
