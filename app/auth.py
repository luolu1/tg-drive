from fastapi import Request, Header, HTTPException
from app.config import API_TOKEN
def verify_api_or_cookie(
    request: Request,
    authorization: str | None = Header(default=None)
):
    if authorization and authorization.startswith("Bearer "):
        if authorization.removeprefix("Bearer ").strip() == API_TOKEN:
            return
    if request.cookies.get("api_token") == API_TOKEN:
        return
    raise HTTPException(status_code=401, detail="Unauthorized")
