import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import Subscription, User


def normalize_email(email: str | None) -> str | None:
    """Lowercased and stripped, or None. Every write and every lookup goes
    through this — `users.email` is unique, so a stray capital or trailing
    space would otherwise create a second account for the same address and
    make the forgot-password lookup miss it."""
    return email.lower().strip() if email else None


def email_taken(db: Session, email: str, *, exclude_user_id: uuid.UUID | None = None) -> bool:
    """`users.email` is UNIQUE, so callers must check before writing —
    otherwise the insert dies on an unhandled UniqueViolation (a 500, not a
    409). `exclude_user_id` is for updates, where the address already
    belonging to the user being edited is not a conflict."""
    query = db.query(User).filter(User.email == email)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None


def _gid_chunk() -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))


def generate_gid() -> str:
    return f"GIO-{_gid_chunk()}-{_gid_chunk()}"


def create_user(db: Session, *, phone_number: str, password: str, display_name: str, language: str, email: str | None = None) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        phone_number=phone_number.strip(),
        email=normalize_email(email),
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
