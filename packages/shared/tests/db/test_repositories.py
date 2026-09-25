import os
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from shared.db.enums import (
    CallbackStatus,
    CallOutcome,
    CallStatus,
    Direction,
    HandoffStatus,
    LanguageCode,
    LeadScore,
    LeadSource,
    LeadStatus,
    MemberRole,
    OrgType,
    Sentiment,
    UsageKind,
    WaMessageType,
    WaStatus,
)
from shared.db.models import CallCreate, LeadCreate, LeadFields, PostCallResult
from shared.db.repositories import (
    AccessDeniedError,
    CallbackRepo,
    CallRepo,
    DncRepo,
    HandoffRepo,
    LeadRepo,
    OrgRepo,
    ProjectRepo,
    SiteVisitRepo,
    SlotUnavailableError,
    UsageRepo,
    VisitSlotRepo,
    WaMessageRepo,
)

# Fixed ids from supabase/seed.sql
BUILDER_ORG = UUID("11111111-1111-4111-8111-111111111111")
BROKER_ORG = UUID("22222222-2222-4222-8222-222222222222")
PROJECT_HINJEWADI = UUID("aaaaaaaa-0000-4000-8000-000000000001")
PROJECT_KHARADI = UUID("aaaaaaaa-0000-4000-8000-000000000002")
CAMPAIGN_BUILDER = UUID("cccccccc-0000-4000-8000-000000000001")

IST = timezone(timedelta(hours=5, minutes=30))
# Real Postgres/Supabase use "Asia/Kolkata"; the embedded Windows build has no tz database,
# so infra/scripts/test_db_embedded.py passes the equivalent POSIX spec instead.
DB_TZ = os.environ.get("TEST_DB_TZ", "Asia/Kolkata")


def _next_weekday_ist(isoweekday: int, hour: int, minute: int = 0) -> datetime:
    start = datetime.now(IST).date() + timedelta(days=1)
    d = start + timedelta(days=(isoweekday - start.isoweekday()) % 7)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)


async def _lead(db, org: UUID = BUILDER_ORG, phone: str = "+919876500001", **kw):
    project_id = kw.pop("project_id", PROJECT_HINJEWADI)
    return await LeadRepo(db).upsert(
        LeadCreate(org_id=org, project_id=project_id, phone=phone, **kw)
    )


# ------------------------------------------------------------- projects ----


async def test_seed_project_config_parses_with_all_languages(db):
    project = await ProjectRepo(db).get(PROJECT_HINJEWADI)
    assert project is not None
    cfg = project.config
    assert cfg.possession.rera_date.year == 2028
    assert {o.key for o in cfg.objections} >= {
        "price_too_high",
        "location_far",
        "possession_delay",
        "loan_emi",
        "already_bought",
        "just_browsing",
        "call_later",
    }
    for item in cfg.faq:
        assert item.a.hi and item.a.mr
    assert cfg.company_display_name.get(LanguageCode.MR) == "सह्याद्री रिअल्टी"


async def test_channel_partner_sees_builder_projects(db):
    repo = ProjectRepo(db)
    builder = {p.id for p in await repo.list_for_org(BUILDER_ORG)}
    broker = {p.id for p in await repo.list_for_org(BROKER_ORG)}
    assert builder == broker == {PROJECT_HINJEWADI, PROJECT_KHARADI}
    assert await repo.get_for_org(BROKER_ORG, PROJECT_KHARADI) is not None

    outsider = await OrgRepo(db).create("Outsider", OrgType.BROKER)
    assert await repo.list_for_org(outsider.id) == []
    assert await repo.get_for_org(outsider.id, PROJECT_KHARADI) is None
    assert not await repo.has_access(outsider.id, PROJECT_KHARADI)


async def test_visit_slots_for_project(db):
    slots = await VisitSlotRepo(db).list_for_project(PROJECT_KHARADI)
    assert slots and all(s.day_of_week != 2 for s in slots)  # closed Tuesdays


# ----------------------------------------------------------------- leads ----


async def test_lead_upsert_dedupes_and_merges_fields(db):
    first = await _lead(db, name=None, fields=LeadFields(bhk="2BHK"))
    second = await _lead(
        db,
        name="Anita Deshpande",
        language_pref=LanguageCode.MR,
        fields=LeadFields(budget_max=9000000),
    )
    assert first.id == second.id
    assert second.name == "Anita Deshpande"
    assert second.language_pref == LanguageCode.MR
    assert second.fields.bhk == "2BHK"
    assert second.fields.budget_max == 9000000


async def test_lead_upsert_dedupes_when_project_is_null(db):
    a = await _lead(db, project_id=None, phone="+919876500002")
    b = await _lead(db, project_id=None, phone="+919876500002", name="X")
    assert a.id == b.id


async def test_lead_rejects_project_without_access(db):
    outsider = await OrgRepo(db).create("Outsider", OrgType.BROKER)
    with pytest.raises(AccessDeniedError):
        await _lead(db, org=outsider.id)


async def test_broker_lead_on_builder_project_is_private_to_broker(db):
    lead = await _lead(db, org=BROKER_ORG, source=LeadSource.META_ADS)
    assert await LeadRepo(db).get(BROKER_ORG, lead.id) is not None
    assert await LeadRepo(db).get(BUILDER_ORG, lead.id) is None


def test_lead_phone_must_be_e164():
    with pytest.raises(ValidationError):
        LeadCreate(org_id=BUILDER_ORG, phone="09876500001")


async def test_find_by_phone_and_status(db):
    lead = await _lead(db)
    found = await LeadRepo(db).find_by_phone(lead.phone, BUILDER_ORG)
    assert [x.id for x in found] == [lead.id]
    await LeadRepo(db).set_status(BUILDER_ORG, lead.id, LeadStatus.QUALIFIED)
    qualified = await LeadRepo(db).list_by_status(BUILDER_ORG, LeadStatus.QUALIFIED)
    assert lead.id in {x.id for x in qualified}


# ------------------------------------------------------------ dnc + dial ----


async def test_dnc_org_and_global(db):
    dnc = DncRepo(db)
    await dnc.add(BUILDER_ORG, "+919876500010", "asked not to call")
    await dnc.add(None, "+919876500011", "TRAI global")
    assert await dnc.is_blocked(BUILDER_ORG, "+919876500010")
    assert not await dnc.is_blocked(BROKER_ORG, "+919876500010")
    assert await dnc.is_blocked(BROKER_ORG, "+919876500011")
    await dnc.add(BUILDER_ORG, "+919876500010")  # idempotent
    await dnc.add(None, "+919876500011")  # idempotent for global (null org) too


async def test_list_dialable_respects_dnc_attempts_and_schedule(db):
    now = datetime.now(UTC)
    repo = LeadRepo(db)
    ok = await _lead(db, phone="+919876500020", campaign_id=CAMPAIGN_BUILDER)
    blocked = await _lead(db, phone="+919876500021", campaign_id=CAMPAIGN_BUILDER)
    exhausted = await _lead(db, phone="+919876500022", campaign_id=CAMPAIGN_BUILDER)
    later = await _lead(db, phone="+919876500023", campaign_id=CAMPAIGN_BUILDER)

    await DncRepo(db).add(BUILDER_ORG, blocked.phone)
    for _ in range(3):
        await repo.record_attempt(BUILDER_ORG, exhausted.id, at=now, next_attempt_at=None)
    await repo.record_attempt(
        BUILDER_ORG, later.id, at=now, next_attempt_at=now + timedelta(hours=1)
    )

    due = await repo.list_dialable(BUILDER_ORG, CAMPAIGN_BUILDER, max_attempts=3, now=now, limit=50)
    assert {x.id for x in due} == {ok.id}


# ----------------------------------------------------------------- calls ----


async def test_call_lifecycle_and_post_call(db):
    lead = await _lead(db)
    calls = CallRepo(db)
    call = await calls.create(
        CallCreate(org_id=BUILDER_ORG, lead_id=lead.id, direction=Direction.OUTBOUND)
    )
    assert call.status == CallStatus.QUEUED
    assert call.transcript == []

    await calls.set_provider_call_id(BUILDER_ORG, call.id, "plivo-uuid-1")
    found = await calls.get_by_provider_id("plivo", "plivo-uuid-1")
    assert found and found.id == call.id

    now = datetime.now(UTC)
    await calls.mark_answered(BUILDER_ORG, call.id, at=now)
    await calls.save_transcript(
        BUILDER_ORG,
        call.id,
        [{"role": "assistant", "text": "नमस्कार"}, {"role": "user", "text": "हो"}],
    )
    ended = await calls.mark_ended(
        BUILDER_ORG,
        call.id,
        status=CallStatus.COMPLETED,
        ended_at=now + timedelta(seconds=95),
        duration_s=95,
        hangup_cause="NORMAL_CLEARING",
    )
    assert ended.duration_s == 95
    assert ended.transcript[0]["text"] == "नमस्कार"

    result = PostCallResult(
        summary="Interested in 2BHK, wants weekend visit",
        score=LeadScore.HOT,
        score_reason="Budget matches, visit requested",
        fields=LeadFields(bhk="2BHK", budget_max=9000000, purpose="live"),
        sentiment=Sentiment.POSITIVE,
        objections=["loan_emi"],
        outcome=CallOutcome.VISIT_BOOKED,
        next_action="Confirm visit on WhatsApp",
    )
    saved = await calls.save_post_call(
        BUILDER_ORG,
        call.id,
        result,
        recording_url="recordings/x.mp3",
        cost_estimate=Decimal("4.2500"),
    )
    assert saved.outcome == CallOutcome.VISIT_BOOKED
    assert saved.objections == ["loan_emi"]

    updated = await LeadRepo(db).apply_post_call(
        BUILDER_ORG, lead.id, result, LeadStatus.VISIT_BOOKED
    )
    assert updated.score == LeadScore.HOT
    assert updated.fields.purpose == "live"
    assert [c.id for c in await calls.list_for_lead(BUILDER_ORG, lead.id)] == [call.id]


async def test_call_cannot_reference_another_orgs_lead(db):
    lead = await _lead(db, org=BROKER_ORG)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await CallRepo(db).create(
            CallCreate(org_id=BUILDER_ORG, lead_id=lead.id, direction=Direction.OUTBOUND)
        )


# ------------------------------------------------------------- callbacks ----


async def test_callbacks_due(db):
    lead = await _lead(db)
    now = datetime.now(UTC)
    repo = CallbackRepo(db)
    due = await repo.create(BUILDER_ORG, lead.id, now - timedelta(minutes=1), reason="busy")
    await repo.create(BUILDER_ORG, lead.id, now + timedelta(days=1))
    assert due.id in {c.id for c in await repo.list_due(now)}
    await repo.set_status(BUILDER_ORG, due.id, CallbackStatus.DONE)
    assert due.id not in {c.id for c in await repo.list_due(now)}


# ----------------------------------------------------------- site visits ----


async def test_site_visit_booking_enforces_slot_and_capacity(db):
    slots = await VisitSlotRepo(db).list_for_project(PROJECT_HINJEWADI)
    monday_morning = next(s for s in slots if s.day_of_week == 1 and s.start_time.hour == 11)
    start = _next_weekday_ist(1, 11)
    end = start + timedelta(minutes=45)
    repo = SiteVisitRepo(db)

    for i in range(monday_morning.capacity):
        lead = await _lead(db, phone=f"+91987650030{i}")
        await repo.book(
            BUILDER_ORG, lead.id, PROJECT_HINJEWADI, monday_morning.id, start, end, tz=DB_TZ
        )

    extra = await _lead(db, phone="+919876500399")
    with pytest.raises(SlotUnavailableError, match="full"):
        await repo.book(
            BUILDER_ORG, extra.id, PROJECT_HINJEWADI, monday_morning.id, start, end, tz=DB_TZ
        )

    evening = _next_weekday_ist(1, 19)
    with pytest.raises(SlotUnavailableError, match="outside"):
        await repo.book(
            BUILDER_ORG,
            extra.id,
            PROJECT_HINJEWADI,
            monday_morning.id,
            evening,
            evening + timedelta(minutes=30),
            tz=DB_TZ,
        )


async def test_broker_can_book_visit_on_builder_project_and_track_reminders(db):
    slots = await VisitSlotRepo(db).list_for_project(PROJECT_KHARADI)
    saturday = next(s for s in slots if s.day_of_week == 6)
    start = _next_weekday_ist(6, saturday.start_time.hour)
    lead = await _lead(db, org=BROKER_ORG, project_id=PROJECT_KHARADI)
    repo = SiteVisitRepo(db)
    visit = await repo.book(
        BROKER_ORG,
        lead.id,
        PROJECT_KHARADI,
        saturday.id,
        start,
        start + timedelta(hours=1),
        tz=DB_TZ,
    )
    visit = await repo.add_reminder(BROKER_ORG, visit.id, {"kind": "t-24h", "channel": "whatsapp"})
    assert visit.reminders_sent == [{"kind": "t-24h", "channel": "whatsapp"}]
    upcoming = await repo.list_upcoming(start - timedelta(minutes=1), start + timedelta(minutes=1))
    assert visit.id in {v.id for v in upcoming}


# ------------------------------------------------- whatsapp/handoff/usage ----


async def test_whatsapp_message_status_flow(db):
    lead = await _lead(db)
    repo = WaMessageRepo(db)
    msg = await repo.create(
        BUILDER_ORG,
        lead.id,
        Direction.OUTBOUND,
        WaMessageType.TEMPLATE,
        {"components": []},
        template_name="project_kit_v1",
    )
    await repo.set_wa_message_id(msg.id, "wamid.TEST123")
    read = await repo.update_status("wamid.TEST123", WaStatus.READ)
    assert read and read.status == WaStatus.READ
    assert await repo.update_status("wamid.unknown", WaStatus.READ) is None


async def test_handoff_and_usage_and_minutes(db):
    lead = await _lead(db)
    call = await CallRepo(db).create(
        CallCreate(org_id=BUILDER_ORG, lead_id=lead.id, direction=Direction.OUTBOUND)
    )
    handoffs = HandoffRepo(db)
    handoff = await handoffs.create(BUILDER_ORG, call.id, "+919800000000")
    handoff = await handoffs.set_status(BUILDER_ORG, handoff.id, HandoffStatus.CONNECTED)
    assert handoff.status == HandoffStatus.CONNECTED

    usage = UsageRepo(db)
    await usage.record(
        BUILDER_ORG, UsageKind.CALL_MINUTE, Decimal("2"), Decimal("1.20"), call_id=call.id
    )
    await usage.record(
        BUILDER_ORG, UsageKind.TTS_CHARS, Decimal("850"), Decimal("0.51"), call_id=call.id
    )
    assert await usage.call_cost(BUILDER_ORG, call.id) == Decimal("1.71")

    orgs = OrgRepo(db)
    before = await orgs.remaining_minutes(BUILDER_ORG)
    await orgs.add_minutes_used(BUILDER_ORG, Decimal("2.5"))
    assert await orgs.remaining_minutes(BUILDER_ORG) == before - Decimal("2.5")


async def test_add_member(db):
    user_id = uuid4()
    await db.execute("insert into auth.users (id, email) values ($1, $2)", user_id, "t@example.com")
    member = await OrgRepo(db).add_member(BUILDER_ORG, user_id, MemberRole.MANAGER)
    assert member.role == MemberRole.MANAGER
