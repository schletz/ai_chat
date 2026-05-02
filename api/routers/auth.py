import datetime
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from dependencies import get_user_repository, get_secret_key, get_algorithm
from user_repository import UserRepository
from schemas import AuthRequest

router = APIRouter()

def create_access_token(data: dict, secret_key: str, algorithm: str) -> str:
    """
    Erstellt ein signiertes JSON Web Token (JWT), welches für 24 Stunden gültig ist.
    Nach Standard wird das Feld 'sub' (Subject) verwendet, um den Benutzernamen zu speichern.
    """
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)

@router.get("/accept-cert")
async def accept_certificate(redirectUrl: str):
    """
    Wird aufgerufen, um im Browser die Zertifikatswarnung (HTTPS/SSL) für selbstsignierte Zertifikate auszulösen.
    Leitet nach der Akzeptanz zurück zur Ziel-URL.
    """
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
    """Benutzer-Login. Überprüft die Zugangsdaten und setzt das JWT als sicheres HttpOnly-Cookie."""
    if not user_repo.authenticate(req.username, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    access_token = create_access_token(data={"sub": req.username}, secret_key=secret_key, algorithm=algorithm)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=24 * 60 * 60,  # 24 hours
    )
    return {"message": "Successfully logged in"}

@router.post("/users/logout")
async def logout(response: Response):
    """Löscht das JWT-Cookie. Da wir zustandslos arbeiten (stateless), ist der Benutzer damit serverseitig sofort abgemeldet."""
    response.delete_cookie(key="access_token", secure=True, samesite="none", httponly=True)
    return {"message": "Successfully logged out"}
