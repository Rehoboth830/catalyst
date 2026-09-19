import os
from fastapi import Header, HTTPException

def require_api_key(x_api_key: str = Header(None)):
    expected = os.environ.get("CATALYST_API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return True