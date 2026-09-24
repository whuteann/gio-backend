import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Subscription, User


def _gid_chunk() -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))


def generate_gid() -> str:
    return f"GIO-{_gid_chunk()}-{_gid_chunk()}"


def create_user(db: Session, *, email: str, password: str, display_name: str, language: str) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name,
        gid=generate_gid(),
        status="ACTIVE",
        preferred_language=language,
        timezone="UTC",
        created_at=now,
    )
    db.add(user)
    db.flush()

    subscription = Subscription(id=uuid.uuid4(), user_id=user.id, plan="FREE", status="ACTIVE", starts_at=now)
    db.add(subscription)
    db.flush()
    return user
