import httpx
import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.config import settings
from backend.models.user import User

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API = "https://api.github.com/user"
GITHUB_EMAILS_API = "https://api.github.com/user/emails"

def get_github_login_url() -> str:
    return f"{GITHUB_AUTHORIZE_URL}?client_id={settings.github_client_id}&scope=repo,user:email"

def exchange_code_for_token(code: str) -> str:
    data = {
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "code": code,
    }
    headers = {"Accept": "application/json"}
    
    with httpx.Client() as client:
        response = client.post(GITHUB_ACCESS_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        
    access_token = result.get("access_token")
    if not access_token:
        raise ValueError("Failed to obtain access token from GitHub")
    return access_token

def fetch_user_profile(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    with httpx.Client() as client:
        # Get basic profile
        profile_response = client.get(GITHUB_USER_API, headers=headers)
        profile_response.raise_for_status()
        profile_data = profile_response.json()
        
        # GitHub email might be private, so fetch from emails endpoint if needed
        email = profile_data.get("email")
        if not email:
            emails_response = client.get(GITHUB_EMAILS_API, headers=headers)
            emails_response.raise_for_status()
            emails_data = emails_response.json()
            # Find primary and verified email
            for em in emails_data:
                if em.get("primary") and em.get("verified"):
                    email = em.get("email")
                    break
            
        profile_data["email"] = email
        return profile_data

def get_or_create_user(db: Session, github_data: dict, access_token: str) -> User:
    github_id = str(github_data.get("id"))
    email = github_data.get("email")
    username = github_data.get("login")
    avatar = github_data.get("avatar_url")
    
    user = db.query(User).filter(User.github_id == github_id).first()
    
    if user:
        # Update details in case they changed
        user.email = email
        user.username = username
        user.avatar = avatar
        user.github_access_token = access_token
        db.commit()
        db.refresh(user)
        return user
        
    # Check if user exists by email (if email is returned)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.github_id = github_id
            user.username = username
            user.avatar = avatar
            user.github_access_token = access_token
            db.commit()
            db.refresh(user)
            return user
            
    # Create new user
    new_user = User(
        github_id=github_id,
        email=email,
        username=username,
        avatar=avatar,
        github_access_token=access_token
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def create_jwt(user: User) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "iat": now,
        "exp": expire
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return token
