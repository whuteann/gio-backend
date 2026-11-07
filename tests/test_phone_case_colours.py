import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.phone_case_colours import _REVIEWED_ARTWORK, matching_cases, product_colour_keys


def candidate(key="forest", identifier="green"):
    return {"id": identifier, "name": identifier, "colour_keys": [key], "price": "129",
            "currency": "MYR", "design_description": "Trees symbolise steady growth."}


def reasons():
    return {"reason_en": "Green matches your colour; trees remind you to grow steadily.",
            "reason_zh": "绿色与你的推荐颜色匹配，树木提醒你稳步成长。",
            "reason_ms": "Hijau sepadan dengan warna anda; pokok mengingatkan anda untuk terus berkembang."}


class CatalogueColourTests(unittest.TestCase):
    def test_graphql_error_does_not_become_empty_success(self):
        from app.services.lumenart import _fetch_all_products
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"errors": [{"message": "Unavailable"}]})
        client = SimpleNamespace(post=lambda *a, **k: response)
        with self.assertRaises(ValueError):
            _fetch_all_products(client, "qa-not-a-real-token")

    def test_partial_pagination_is_not_accepted(self):
        from app.services.lumenart import _fetch_all_products
        payloads = iter([{"data": {"products": {"nodes": [{"id": "first"}],
            "pageInfo": {"hasNextPage": True, "endCursor": "next"}}}}, {"errors": [{"message": "Unavailable"}]}])
        client = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=lambda: next(payloads)))
        with self.assertRaises(ValueError):
            _fetch_all_products(client, "qa-not-a-real-token")

    def test_known_artwork_and_changed_image(self):
        identifier, (image, key) = next(iter(_REVIEWED_ARTWORK.items()))
        raw = {"id": identifier, "featuredMedia": {"image": {"url": image}}}
        self.assertEqual(product_colour_keys(raw), [key])
        raw["featuredMedia"]["image"]["url"] += "-changed"
        self.assertEqual(product_colour_keys(raw), [])

    def test_no_colour_guessed_from_name_or_description(self):
        self.assertEqual(product_colour_keys({"id": "new", "title": "Red energy", "description": "red"}), [])
        self.assertEqual(matching_cases([candidate(), {"id": "red", "name": "Scarlet"}], "scarlet"), [])

    def test_explicit_metadata_including_empty_and_invalid_overrides_review(self):
        identifier, (image, _) = next(iter(_REVIEWED_ARTWORK.items()))
        raw = {"id": identifier, "featuredMedia": {"image": {"url": image}}}
        for value, expected in [('[]', []), ('["forest","forest"]', ["forest"]),
                                ('["pink"]', []), ('"scarlet"', []), ('broken', [])]:
            raw["aurenColours"] = {"type": "list.single_line_text_field", "value": value}
            self.assertEqual(product_colour_keys(raw), expected)

    def test_matching_is_exact_and_unknown_key_fails_closed(self):
        blue, green = candidate("ocean", "blue"), candidate()
        self.assertEqual(matching_cases([blue, green], "ocean"), [blue])
        self.assertEqual(matching_cases([blue, green], "unknown"), [])


class AIColourTests(unittest.IsolatedAsyncioTestCase):
    async def test_combined_stone_and_case_schema_has_only_matched_cases(self):
        from app.services import ai_recommendation as ai
        async def respond(**kwargs):
            schema = kwargs["text_format"]
            case_model = schema.model_fields["primary_case_pick"].annotation
            self.assertEqual([m.value for m in case_model.model_fields["case_key"].annotation], ["C01"])
            self.assertNotIn("blue-only-design", kwargs["input"][1]["content"])
            data = {f"letter_{lang}": "QA letter" for lang in ("en", "zh", "ms")}
            data.update(feature_pick={"product_key": "F01", "material_tag": "Jade", **reasons()},
                        primary_case_pick={"case_key": "C01", **reasons()})
            return SimpleNamespace(output_parsed=schema(**data))
        with patch.object(ai._client.responses, "parse", new=AsyncMock(side_effect=respond)):
            result = await ai.generate_recommendation(narrative_prompt="Pressure", focus_label="Releasing pressure",
                material_affinity="Jade", stone_candidates_by_type={"Jade": [{"id": "stone", "name": "Jade"}]},
                phone_case_candidates=[candidate("ocean", "blue-only-design"), candidate()], colour_key="forest")
        self.assertEqual(result["feature"]["id"], "stone")
        self.assertEqual(result["phone_case"][0]["id"], "green")

    async def test_no_match_skips_model(self):
        from app.services import ai_recommendation as ai
        with patch.object(ai._client.responses, "parse", new=AsyncMock()) as model:
            picks = await ai.generate_phone_case_recommendation(
                narrative_prompt="Low energy", colour_key="scarlet", phone_case_candidates=[candidate()])
        self.assertEqual(picks, [])
        model.assert_not_awaited()

    async def test_schema_excludes_other_colours_and_prompt_explains_design(self):
        from app.services import ai_recommendation as ai
        async def respond(**kwargs):
            schema = kwargs["text_format"]
            pick_model = schema.model_fields["primary_case_pick"].annotation
            values = [m.value for m in pick_model.model_fields["case_key"].annotation]
            self.assertEqual(values, ["C01"])
            self.assertNotIn("secondary_case_pick", schema.model_fields)
            prompt = kwargs["input"][1]["content"]
            self.assertIn("colour first", prompt)
            self.assertIn("Trees symbolise steady growth", prompt)
            self.assertNotIn("blue-only-design", prompt)
            return SimpleNamespace(output_parsed=schema(primary_case_pick={"case_key": "C01", **reasons()}))
        with patch.object(ai._client.responses, "parse", new=AsyncMock(side_effect=respond)):
            result = await ai.generate_phone_case_recommendation(narrative_prompt="Pressure is high",
                colour_key="forest", phone_case_candidates=[candidate("ocean", "blue-only-design"), candidate()])
        self.assertEqual([p["id"] for p in result], ["green"])

    async def test_no_stones_does_not_block_matching_case(self):
        from app.services import ai_recommendation as ai
        with patch.object(ai, "generate_phone_case_recommendation", new=AsyncMock(return_value=[candidate()])) as cases:
            result = await ai.generate_recommendation(narrative_prompt="Pressure", focus_label="Releasing pressure",
                material_affinity="Jade", stone_candidates_by_type={"Jade": []},
                phone_case_candidates=[candidate()], colour_key="forest")
        self.assertEqual(result["feature"], None)
        self.assertEqual(result["phone_case"][0]["id"], "green")
        cases.assert_awaited_once()


@unittest.skipUnless(os.getenv("AUREN_TEST_DATABASE") == "auren_colour_qa", "requires isolated PostgreSQL QA database")
class ColourIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.config import settings
        if not settings.database_url.rstrip("/").endswith("/auren_colour_qa"):
            raise RuntimeError("Tests refuse production databases")
        import app.models
        from app.database import SessionLocal
        cls.Session = staticmethod(SessionLocal)

    def setUp(self):
        from app.models.lumenart import LumenartProduct
        from app.models.user import User
        from app.models.reflection import InnerReading, InnerStateSnapshot
        from app.models.recommendation import RecommendationProfile
        from app.services.recommendation import _product_item, _phone_case_item
        self.db = self.Session()
        self.db.query(LumenartProduct).delete()
        self.db.add_all([LumenartProduct(id=c["id"], title=c["name"], handle=c["id"],
            colour_keys=c["colour_keys"], fetched_at=datetime.now(timezone.utc))
            for c in [candidate(), candidate("ocean", "blue")]])
        self.user = User(phone_number="999" + str(uuid.uuid4().int)[:10], password_hash="qa", display_name="QA", gid=uuid.uuid4().hex)
        self.db.add(self.user)
        self.db.flush()
        reading = InnerReading(user_id=self.user.id, ordinal=1, blueprint_version="qa", started_at=datetime.now(timezone.utc))
        self.db.add(reading)
        self.db.flush()
        snapshot = InnerStateSnapshot(user_id=self.user.id, source_type="INNER_READING", inner_reading_id=reading.id,
            emotional_energy=70, mental_clarity=70, inner_pressure=85, grounding=70)
        self.db.add(snapshot)
        self.db.flush()
        self.snapshot = snapshot
        self.profile = RecommendationProfile(user_id=self.user.id, state_snapshot_id=snapshot.id,
            trigger_type="INNER_READING", trigger_inner_reading_id=reading.id, current_focus="Releasing pressure",
            summary="QA", colour_key="forest", recommendation_date=datetime.now(timezone.utc).date(), status="READY")
        self.profile.items.append(_product_item({"id": "stone", "name": "Existing stone", **reasons()}, rank=3))
        self.profile.items.append(_phone_case_item({**candidate(), **reasons()}, rank=4))
        self.db.add(self.profile)
        self.db.flush()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def sync(self, key, picks=None, failure=False):
        from app.services.recommendation import _sync_phone_case_items
        model = AsyncMock(side_effect=RuntimeError("QA transient") if failure else None,
                          return_value=picks if picks is not None else [{**candidate(key, "blue" if key == "ocean" else "green"), **reasons()}])
        with patch("app.services.recommendation.generate_phone_case_recommendation", new=model):
            _sync_phone_case_items(self.profile, db=self.db, colour_key=key, narrative_prompt_factory=lambda: "QA reflection")
            self.db.flush()
        return model

    def test_red_removes_old_green_and_never_calls_model(self):
        stone_id = self.profile.items[0].id
        model = self.sync("scarlet")
        model.assert_not_awaited()
        self.assertFalse(any(i.type == "PHONE_CASE" for i in self.profile.items))
        self.assertEqual(self.profile.items[0].id, stone_id)
        self.assertEqual(self.profile.phone_case_status, "NO_MATCH")

    def test_changed_colour_replaces_case_but_preserves_stone_and_letter(self):
        self.profile.phone_case_colour_key = "forest"
        self.profile.phone_case_status = "READY"
        self.profile.letter_ms = "Existing Malay letter"
        stone_id = self.profile.items[0].id
        self.sync("ocean").assert_awaited_once()
        self.assertEqual([i.reference_id for i in self.profile.items if i.type == "PHONE_CASE"], ["blue"])
        self.assertEqual(self.profile.items[0].id, stone_id)
        self.assertEqual(self.profile.letter_ms, "Existing Malay letter")
        self.sync("ocean").assert_not_awaited()

    def test_model_failure_removes_mismatch_and_has_bounded_retry(self):
        self.sync("ocean", failure=True).assert_awaited_once()
        self.assertFalse(any(i.type == "PHONE_CASE" for i in self.profile.items))
        self.assertEqual(self.profile.phone_case_status, "UNAVAILABLE")
        self.sync("ocean").assert_not_awaited()
        self.profile.phone_case_checked_at -= timedelta(minutes=11)
        self.sync("ocean").assert_awaited_once()

    def test_historical_serialization_hides_mismatched_case_without_mutating(self):
        from app.api.v1.endpoints.recommendations import _serialize
        self.profile.colour_key = "scarlet"
        out = _serialize(self.profile, self.db)
        self.assertEqual(out.phone_case_status, "NO_MATCH")
        self.assertFalse(any(i.type == "PHONE_CASE" for i in out.items))
        self.assertTrue(any(i.type == "PHONE_CASE" for i in self.profile.items))

    def test_catalogue_change_invalidates_previously_matching_case(self):
        from app.models.lumenart import LumenartProduct
        self.profile.phone_case_colour_key = "forest"
        self.profile.phone_case_status = "READY"
        self.db.get(LumenartProduct, "green").colour_keys = []
        self.db.flush()
        self.sync("forest").assert_not_awaited()
        self.assertFalse(any(i.type == "PHONE_CASE" for i in self.profile.items))

    def test_build_changes_colour_without_rebuilding_daily_stones(self):
        from app.services.recommendation import build_recommendation
        stone_id = self.profile.items[0].id
        with patch("app.services.recommendation._refresh_product_items") as stone_step:
            profile = build_recommendation(self.db, user=self.user, snapshot=self.snapshot,
                core_personality_id=None, focus_key="emotional_energy", personality_title=None,
                trigger_type="INNER_READING", trigger_check_in_session_id=None,
                trigger_inner_reading_id=self.snapshot.inner_reading_id)
        stone_step.assert_not_called()
        self.assertEqual(profile.colour_key, "scarlet")
        self.assertEqual([i.id for i in profile.items if i.type == "PRODUCT"], [stone_id])
        self.assertFalse(any(i.type == "PHONE_CASE" for i in profile.items))

    def test_stone_retry_preserves_stable_case_without_duplicate(self):
        from app.services.recommendation import build_recommendation
        for item in [i for i in self.profile.items if i.type == "PRODUCT"]:
            self.profile.items.remove(item)
            self.db.delete(item)
        self.profile.phone_case_colour_key = "forest"
        self.profile.phone_case_status = "READY"
        old_case_id = next(i.id for i in self.profile.items if i.type == "PHONE_CASE")
        empty = {"feature": None, "others": [], "phone_case": []}
        with patch("app.services.recommendation._fetch_and_pick", new=AsyncMock(return_value=empty)) as stones:
            with patch("app.services.recommendation.generate_phone_case_recommendation", new=AsyncMock()) as cases:
                build_recommendation(self.db, user=self.user, snapshot=self.snapshot, core_personality_id=None,
                    focus_key="inner_pressure", personality_title=None, trigger_type="INNER_READING",
                    trigger_check_in_session_id=None, trigger_inner_reading_id=self.snapshot.inner_reading_id)
        self.assertFalse(stones.await_args.kwargs["include_phone_cases"])
        cases.assert_not_awaited()
        self.assertEqual([i.id for i in self.profile.items if i.type == "PHONE_CASE"], [old_case_id])


if __name__ == "__main__":
    unittest.main()
