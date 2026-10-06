# Import every model module so `Base.metadata` (and therefore Alembic
# autogenerate) sees all tables, even though nothing else in the app needs
# to import from this package directly.
from app.models import gamification, journal, lumenart, narrative, payment, personality, recommendation, reflection, user  # noqa: F401
