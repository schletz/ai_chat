import datetime
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from dependencies import get_user_repository, get_secret_key, get_algorithm
from user_repository import UserRepository
from schemas import AuthRequest

router = APIRouter()


def create_token(data: dict, secret_key: str, algorithm: str, expires_delta: datetime.timedelta) -> str:
    """
    Generate a signed JWT with a configurable expiration delta.

    @param data: Payload to encode.
    @param secret_key: Cryptographic key for signing.
    @param algorithm: Hashing algorithm.
    @param expires_delta: Time offset from now until the token expires.
    """
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


@router.get("/accept-cert")
async def accept_certificate(redirectUrl: str):
    """Redirect the client to the target URL with a certificate acceptance flag."""
    separator = "&" if "?" in redirectUrl else "?"
    final_url = f"{redirectUrl}{separator}certificateAccepted=true"
    return Response(status_code=status.HTTP_302_FOUND, headers={"Location": final_url})


@router.post("/users/auth")
async def authenticate_user(
    req: AuthRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
    secret_key: str = Depends(get_secret_key),
    algorithm: str = Depends(get_algorithm)
):
    """Authenticate credentials and issue secure HttpOnly JWT cookies for access and refresh."""
    if not user_repo.authenticate(req.username, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # 1 hour for access, 7 days for refresh
    access_token = create_token({"sub": req.username}, secret_key, algorithm, datetime.timedelta(hours=1))
    refresh_token = create_token({"sub": req.username, "type": "refresh"}, secret_key, algorithm, datetime.timedelta(days=7))

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=3600
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=7 * 24 * 3600
    )

    return {"message": "Successfully logged in"}


@router.post("/users/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    secret_key: str = Depends(get_secret_key),
    algorithm: str = Depends(get_algorithm)
):
    """Validate the refresh token and issue a new pair of access and refresh tokens."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token provided")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        username = str(payload.get("sub"))
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        # Re-issue tokens to rotate the refresh token and reset the session duration
        new_access_token = create_token({"sub": username}, secret_key, algorithm, datetime.timedelta(hours=1))
        new_refresh_token = create_token({"sub": username, "type": "refresh"}, secret_key, algorithm, datetime.timedelta(days=7))

        response.set_cookie(
            key="access_token", value=new_access_token, httponly=True, secure=True, samesite="none", max_age=3600
        )
        response.set_cookie(
            key="refresh_token", value=new_refresh_token, httponly=True, secure=True, samesite="none", max_age=7 * 24 * 3600
        )

        return {"message": "Token successfully refreshed"}

    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid or expired") from e


@router.post("/users/logout")
async def logout(response: Response):
    """Remove both JWT cookies to invalidate the client-side session."""
    cookie_kwargs = {"secure": True, "samesite": "none", "httponly": True}
    response.delete_cookie(key="access_token", **cookie_kwargs)
    response.delete_cookie(key="refresh_token", **cookie_kwargs)
    return {"message": "Successfully logged out"}
