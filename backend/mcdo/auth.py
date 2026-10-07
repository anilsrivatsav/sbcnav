import hmac
import os
import base64
import hashlib
import json
import secrets
import time
from fastapi import Header, HTTPException

def administrator(authorization: str | None = Header(None)):
    token=os.getenv('MCDO_ADMIN_TOKEN','')
    if len(token)<32:
        raise HTTPException(503,'MCDO operator access has not been configured on Oracle.')
    supplied=(authorization or '').removeprefix('Bearer ')
    valid=hmac.compare_digest(supplied,token)
    if supplied.startswith('mcdo.'):
        try:
            prefix,payload,signature=supplied.split('.')
            expected=hmac.new(token.encode(),payload.encode(),hashlib.sha256).hexdigest()
            claims=json.loads(base64.urlsafe_b64decode(payload+'='*((-len(payload))%4)))
            valid=hmac.compare_digest(signature,expected) and claims.get('aud')=='mcdo' and isinstance(claims.get('exp'),int) and time.time()<claims['exp']<=time.time()+8*3600+60
        except (ValueError,TypeError,KeyError):valid=False
    if not authorization or not authorization.startswith('Bearer ') or not valid:
        raise HTTPException(401,'Enter the MCDO operator access key.')

def issue_session():
    expires=int(time.time())+8*3600
    payload=base64.urlsafe_b64encode(json.dumps({'aud':'mcdo','exp':expires,'nonce':secrets.token_hex(16)},separators=(',',':')).encode()).decode().rstrip('=')
    signature=hmac.new(os.environ['MCDO_ADMIN_TOKEN'].encode(),payload.encode(),hashlib.sha256).hexdigest()
    return {'session_token':'mcdo.'+payload+'.'+signature,'expires_at':expires}
