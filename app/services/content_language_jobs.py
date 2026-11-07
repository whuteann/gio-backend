"""One durable job per result/language; bounded retries survive worker restarts."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.models.content_language_job import ContentLanguageJob as Job
from app.services import languages
from app.services.content_languages import mark_actual_languages, missing, repair_one

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 4
LEASE_SECONDS = 600
GENERATION_TIMEOUT_SECONDS = 240


def utcnow():
    return datetime.now(timezone.utc)


def enqueue_missing(db, kind, row, preferred=None):
    mark_actual_languages(row, kind)
    preferred = languages.normalize(preferred)
    order = [preferred] + [code for code in languages.SUPPORTED if code != preferred]
    for code in order:
        if not missing(row, kind, code):
            continue
        statement = insert(Job).values(
            id=uuid.uuid4(), user_id=row.user_id, kind=kind, entity_id=row.id,
            language=code, status="PENDING", attempts=0, next_attempt_at=utcnow(),
        ).on_conflict_do_nothing(constraint="uq_content_language_job")
        db.execute(statement)


def claim_job(db):
    now = utcnow()
    # A process can stop after claiming a job. Its lease expires, so that
    # request is recovered without resetting its bounded attempt counter.
    stale = db.query(Job).filter(Job.status == "RUNNING", Job.locked_at < now - timedelta(seconds=LEASE_SECONDS)).with_for_update(skip_locked=True).all()
    for job in stale:
        job.status = "FAILED" if job.attempts >= MAX_ATTEMPTS else "RETRY"
        job.next_attempt_at = now
        job.locked_at = None
        job.error_type = "WorkerLeaseExpired"
    job = db.query(Job).filter(
        Job.status.in_(("PENDING", "RETRY")), Job.next_attempt_at <= now,
        Job.attempts < MAX_ATTEMPTS,
    ).order_by(Job.next_attempt_at, Job.created_at, Job.id).with_for_update(skip_locked=True).first()
    if job is None:
        db.commit()
        return None
    job.status = "RUNNING"
    job.attempts += 1
    job.locked_at = now
    claimed = (job.id, job.kind, job.entity_id, job.language, job.attempts)
    db.commit()
    return claimed


def finish_job(db, job_id, attempt, error_type=None, cancelled=False):
    job = db.query(Job).filter_by(id=job_id).with_for_update().first()
    # Ignore a late completion after another worker reclaimed the lease.
    if job is None or job.status != "RUNNING" or job.attempts != attempt:
        return
    job.locked_at = None
    job.error_type = error_type
    if error_type or cancelled:
        if cancelled:
            job.attempts = max(0, job.attempts - 1)
        job.status = "FAILED" if job.attempts >= MAX_ATTEMPTS else "RETRY"
        job.next_attempt_at = utcnow() + timedelta(seconds=min(300, 10 * 2 ** max(0, job.attempts - 1)))
    else:
        job.status = "DONE"
        job.completed_at = utcnow()
    db.commit()


async def run_next_job():
    with SessionLocal() as db:
        claimed = claim_job(db)
    if claimed is None:
        return False
    job_id, kind, entity_id, language, attempt = claimed
    error = None
    cancelled = False
    try:
        with SessionLocal() as db:
            await asyncio.wait_for(repair_one(db, kind, entity_id, language), GENERATION_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        cancelled = True
        raise
    except Exception as exc:
        # Do not store or log prompts, source text, credentials, or response bodies.
        error = type(exc).__name__
        logger.warning("Language job %s attempt %s failed (%s).", job_id, attempt, error)
    finally:
        with SessionLocal() as db:
            finish_job(db, job_id, attempt, error, cancelled)
    return True


async def worker(stop):
    while not stop.is_set():
        try:
            if await run_next_job():
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Language queue unavailable (%s).", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
