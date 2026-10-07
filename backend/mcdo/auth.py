import hmac
import os
from fastapi import Header, HTTPException

def administrator(authorization: str | None = Header(None)):
    token=os.getenv('MCDO_ADMIN_TOKEN','')
    if len(token)<32:
        raise HTTPException(503,'MCDO operator access has not been configured on Oracle.')
    if not authorization or not hmac.compare_digest(authorization,'Bearer '+token):
        raise HTTPException(401,'Enter the MCDO operator access key.')
