"""Run only against the explicitly named, disposable PostgreSQL QA database."""
import asyncio
import os
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch


@unittest.skipUnless(os.getenv("AUREN_TEST_DATABASE") == "auren_language_qa", "requires isolated PostgreSQL QA database")
class LanguageQueueIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.models
        from app.config import settings
        if not settings.database_url.rstrip("/").endswith("/auren_language_qa"):
            raise RuntimeError("Tests refuse to use a non-QA database")
        settings.language_worker_enabled = False
        from app.database import SessionLocal
        from app.main import app as api
        from app.models.content_language_job import ContentLanguageJob
        from app.models.personality import CorePersonality
        from app.models.reflection import InnerReading
        from app.models.user import User, Subscription
        from app.schemas.ai_personality import CorePersonalityGeneration
        from app.services import content_language_jobs
        cls.Session = staticmethod(SessionLocal)
        cls.api, cls.Job, cls.Personality, cls.Reading = api, ContentLanguageJob, CorePersonality, InnerReading
        cls.User, cls.Subscription, cls.Generation, cls.jobs = User, Subscription, CorePersonalityGeneration, content_language_jobs

    def setUp(self):
        from fastapi import Depends
        from fastapi.testclient import TestClient
        from app.dependencies import get_current_user, get_db
        self.db = self.Session()
        self.user = self.User(id=uuid.uuid4(), phone_number="999" + str(uuid.uuid4().int)[:10],
            password_hash="qa-no-login", display_name="Language QA", gid="QA-" + uuid.uuid4().hex,
            birthdate=date(1990, 1, 1), preferred_language="ms", email_verified_at=datetime.now(timezone.utc))
        self.db.add(self.user)
        self.db.flush()
        self.db.add(self.Subscription(user_id=self.user.id, plan="FREE", status="ACTIVE"))
        self.db.commit()
        def current_user(db=Depends(get_db)):
            return db.get(self.User, self.user.id)
        self.api.dependency_overrides[get_current_user] = current_user
        self.client = TestClient(self.api)

    def tearDown(self):
        self.client.close()
        self.api.dependency_overrides.clear()
        self.db.rollback()
        self.db.query(self.User).filter_by(id=self.user.id).delete()
        self.db.commit()
        self.db.close()

    def generated(self, language="ms"):
        return self.Generation(title=f"Sinar Penyayang {language}", subtitle="Kehangatan yang menyatukan",
            overview="Anda membawa ketenangan dan perhatian kepada orang di sekeliling.", summary="Keprihatinan dan kreativiti.",
            **{name: [{"emoji": "🌱", "text": "Perhatian anda membantu orang lain berkembang."}] * 3
               for name in ("birthday_number_points", "life_path_number_points", "talent_number_points")})

    def personality(self):
        row = self.Personality(user_id=self.user.id, primary_language="en", generation_status="READY",
            languages_ready=["en", "zh"], birthday_number=1, life_path_number=3, talent_number="12/3",
            scarlet_score=10, russet_score=10, gold_score=10, forest_score=10, ocean_score=20)
        for language in ("en", "zh"):
            for name, value in self.generated(language).model_dump().items():
                setattr(row, f"{name}_{language}", value)
        self.db.add(row)
        self.db.commit()
        return row

    def test_new_ms_account_and_idempotent_calculation_queue_each_other_language_once(self):
        with patch("app.api.v1.endpoints.core_personality.generate_core_personality_content", new=AsyncMock(return_value=self.generated())) as model:
            response = self.client.post("/api/v1/core-personality/calculate", json={"date_of_birth": "1990-01-01", "language": "ms"})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["languages_ready"], ["ms"])
            self.assertEqual(response.json()["title_ms"], self.generated().title)
            again = self.client.post("/api/v1/core-personality/calculate", json={"date_of_birth": "1990-01-01", "language": "ms"})
            self.assertEqual(again.status_code, 200)
            self.assertEqual(model.await_count, 1)
        self.assertEqual(self.db.query(self.Job).filter_by(user_id=self.user.id).count(), 2)
        with patch("app.services.ai_personality.generate_core_personality_content", new=AsyncMock(side_effect=lambda **kw: self.generated(kw["language"]))):
            for _ in range(2):
                self.assertTrue(asyncio.run(self.jobs.run_next_job()))
        result = self.client.get("/api/v1/core-personality/current").json()
        self.assertEqual(result["languages_ready"], ["en", "zh", "ms"])
        self.assertEqual(result["title_ms"], self.generated().title)

    def test_switch_from_en_to_ms_recovers_transient_failure_without_replacing_english(self):
        row = self.personality()
        original = row.title_en
        self.assertEqual(self.client.get("/api/v1/core-personality/current").status_code, 200)
        with patch("app.services.ai_personality.generate_core_personality_content", new=AsyncMock(side_effect=RuntimeError("temporary"))):
            asyncio.run(self.jobs.run_next_job())
        self.db.expire_all()
        job = self.db.query(self.Job).filter_by(entity_id=row.id, language="ms").one()
        self.assertEqual((job.status, job.attempts), ("RETRY", 1))
        job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()
        with patch("app.services.ai_personality.generate_core_personality_content", new=AsyncMock(return_value=self.generated())):
            asyncio.run(self.jobs.run_next_job())
        result = self.client.get("/api/v1/core-personality/current").json()
        self.assertEqual(result["title_en"], original)
        self.assertEqual(result["title_ms"], self.generated().title)
        self.db.expire_all()
        self.assertEqual(self.db.get(self.Job, job.id).status, "DONE")

    def test_retry_limit_is_persistent_and_repeated_reads_do_not_reset_it(self):
        row = self.personality()
        self.client.get("/api/v1/core-personality/current")
        with patch("app.services.ai_personality.generate_core_personality_content", new=AsyncMock(side_effect=RuntimeError("temporary"))):
            for _ in range(self.jobs.MAX_ATTEMPTS):
                self.db.expire_all()
                job = self.db.query(self.Job).filter_by(entity_id=row.id, language="ms").one()
                job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                self.db.commit()
                asyncio.run(self.jobs.run_next_job())
        self.client.get("/api/v1/core-personality/current")
        self.db.expire_all()
        job = self.db.query(self.Job).filter_by(entity_id=row.id, language="ms").one()
        self.assertEqual((job.status, job.attempts), ("FAILED", self.jobs.MAX_ATTEMPTS))
        self.assertFalse(asyncio.run(self.jobs.run_next_job()))

    def test_crashed_worker_lease_is_reclaimed_and_not_claimed_twice(self):
        row = self.personality()
        self.client.get("/api/v1/core-personality/current")
        job = self.db.query(self.Job).filter_by(entity_id=row.id).one()
        job.status, job.attempts = "RUNNING", 1
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=700)
        self.db.commit()
        with self.Session() as db:
            self.assertIsNone(self.jobs.claim_job(db))
            claimed = self.jobs.claim_job(db)
            self.assertEqual(claimed[-1], 2)
        with self.Session() as db:
            self.assertIsNone(self.jobs.claim_job(db))

    def test_a_concurrent_completed_version_wins_over_the_repair(self):
        from app.services.content_languages import repair_one
        row = self.personality()
        async def concurrent_generation(**kwargs):
            with self.Session() as other:
                stored = other.get(self.Personality, row.id)
                stored.title_ms = "Completed elsewhere"
                other.commit()
            return self.generated()
        with patch("app.services.ai_personality.generate_core_personality_content", new=AsyncMock(side_effect=concurrent_generation)):
            with self.Session() as db:
                asyncio.run(repair_one(db, "personalities", row.id, "ms"))
        self.db.expire_all()
        self.assertEqual(self.db.get(self.Personality, row.id).title_ms, "Completed elsewhere")

    def test_malay_free_and_premium_reading_limits_match_other_languages(self):
        from app.services.scoring import reading_content_for_plan
        from types import SimpleNamespace
        narrative = " ".join(["tenang"] * 150)
        row = SimpleNamespace(emotional_energy=75, mental_clarity=75, inner_pressure=25, grounding=75,
            narrative=narrative, narrative_zh=narrative, narrative_ms=narrative,
            life_area_insights={"work": "content"}, life_area_insights_zh={"work": "content"}, life_area_insights_ms={"work": "content"})
        free = reading_content_for_plan(row, False)
        self.assertIsNone(free["life_area_insights_ms"])
        self.assertLess(len(free["narrative_ms"]), len(narrative))
        premium = reading_content_for_plan(row, True)
        self.assertEqual(premium["narrative_ms"], narrative)
        self.assertEqual(premium["life_area_insights_ms"], {"work": "content"})


if __name__ == "__main__":
    unittest.main()
