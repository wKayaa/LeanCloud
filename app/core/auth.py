import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .models import User
from .config import config_manager


security = HTTPBearer()


class AuthManager:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.lockout_until: Dict[str, datetime] = {}
        self._initialize_default_user()
    
    def _initialize_default_user(self):
        """Initialize default admin user if first run"""
        config = config_manager.get_config()
        if config.first_run:
            # Default password that must be changed on first login
            default_password = "admin123"
            self.users["admin"] = User(
                username="admin",
                role="admin",
                password_hash=self._hash_password(default_password),
                created_at=datetime.now()
            )
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def _is_locked_out(self, username: str) -> bool:
        """Check if user is locked out due to failed attempts"""
        if username in self.lockout_until:
            if datetime.now() < self.lockout_until[username]:
                return True
            else:
                # Lockout expired, clear it
                del self.lockout_until[username]
                self.failed_attempts[username] = 0
        return False
    
    def _record_failed_attempt(self, username: str):
        """Record failed login attempt and apply lockout if needed"""
        self.failed_attempts[username] = self.failed_attempts.get(username, 0) + 1
        if self.failed_attempts[username] >= 5:  # 5 failed attempts
            self.lockout_until[username] = datetime.now() + timedelta(minutes=15)
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        if self._is_locked_out(username):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked due to too many failed attempts"
            )
        
        user = self.users.get(username)
        if not user or not self._verify_password(password, user.password_hash):
            self._record_failed_attempt(username)
            return None
        
        # Clear failed attempts on successful login
        self.failed_attempts[username] = 0
        user.last_login = datetime.now()
        return user
    
    def create_access_token(self, username: str, role: str = "admin") -> str:
        """Create JWT access token"""
        config = config_manager.get_config()
        expire = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "sub": username,
            "role": role,
            "exp": expire
        }
        return jwt.encode(payload, config.secret_key, algorithm="HS256")
    
    def verify_token(self, token: str) -> Dict:
        """Verify JWT token and return payload"""
        try:
            config = config_manager.get_config()
            payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        user = self.users.get(username)
        if not user:
            return False
        
        if not self._verify_password(old_password, user.password_hash):
            return False
        
        user.password_hash = self._hash_password(new_password)
        
        # If this was first run, mark it as complete
        from .settings import get_settings
        settings = get_settings()
        if settings.first_run:
            # Update the first_run flag (in a real implementation, this would persist to database)
            settings.first_run = False
        
        return True
    
    def is_first_run(self) -> bool:
        """Check if this is the first run requiring password change"""
        from .settings import get_settings
        settings = get_settings()
        return settings.first_run


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """FastAPI dependency to get current authenticated user"""
    payload = auth_manager.verify_token(credentials.credentials)
    return payload


def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """FastAPI dependency to require admin role"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return current_user


# Global auth manager instance
auth_manager = AuthManager()