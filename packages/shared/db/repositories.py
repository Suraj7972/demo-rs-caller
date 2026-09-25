"""Thin async repositories over asyncpg.

Rules:
- Every tenant-scoped method takes `org_id` and filters by it (the backend bypasses RLS).
- Methods accept either a Pool or a Connection, so callers (and tests) can wrap several
  calls in one transaction by passing a connection.
- SQL stays here; business rules (calling window, retry policy, etc.) live elsewhere.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from shared.db.enums import (
    CallbackStatus,
    CallStatus,
    CampaignStatus,
    Direction,
    HandoffStatus,
    LeadStatus,
    MemberRole,
    OrgType,
    UsageKind,
    VisitStatus,
    WaMessageType,
    WaStatus,
)
from shared.db.models import (
    Call,
    Callback,
    CallCreate,
    Campaign,
    DncEntry,
    Handoff,
    Lead,
    LeadCreate,
    LeadFields,
    Org,
    OrgMember,
    PostCallResult,
    Project,
    SiteVisit,
    UsageEvent,
    VisitSlot,
    WaMessage,
)

Executor = asyncpg.Pool | asyncpg.Connection
M = TypeVar("M", bound=BaseModel)

DEFAULT_TZ = "Asia/Kolkata"


class RepositoryError(Exception):
    pass


class NotFoundError(RepositoryError):
    pass


class AccessDeniedError(RepositoryError):
    """Org tried to use a project it neither owns nor has project_access to."""


class SlotUnavailableError(RepositoryError):
    """Requested visit time doesn't fit the slot, or the slot is full."""


@asynccontextmanager
async def transaction(db: Executor) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection inside a transaction (savepoint if already in one)."""
    if isinstance(db, asyncpg.Pool):
        async with db.acquire() as conn, conn.transaction():
            yield conn
    else:
        async with db.transaction():
            yield db


class _Repo:
    def __init__(self, db: Executor) -> None:
        self.db = db

    async def _one(self, model: type[M], sql: str, *args: Any) -> M | None:
        row = await self.db.fetchrow(sql, *args)
        return model.model_validate(dict(row)) if row else None

    async def _one_or_raise(self, model: type[M], sql: str, *args: Any) -> M:
        found = await self._one(model, sql, *args)
        if found is None:
            raise NotFoundError(model.__name__)
        return found

    async def _many(self, model: type[M], sql: str, *args: Any) -> list[M]:
        rows = await self.db.fetch(sql, *args)
        return [model.model_validate(dict(r)) for r in rows]


# ------------------------------------------------------------------ orgs ----


class OrgRepo(_Repo):
    async def get(self, org_id: UUID) -> Org | None:
        return await self._one(Org, "select * from public.orgs where id = $1", org_id)

    async def create(self, name: str, type: OrgType, *, minutes_quota: int = 0) -> Org:
        return await self._one_or_raise(
            Org,
            "insert into public.orgs (name, type, minutes_quota) values ($1, $2, $3) returning *",
            name,
            type,
            minutes_quota,
        )

    async def add_member(self, org_id: UUID, user_id: UUID, role: MemberRole) -> OrgMember:
        return await self._one_or_raise(
            OrgMember,
            """insert into public.org_members (org_id, user_id, role) values ($1, $2, $3)
               on conflict (org_id, user_id) do update set role = excluded.role
               returning *""",
            org_id,
            user_id,
            role,
        )

    async def add_minutes_used(self, org_id: UUID, minutes: Decimal) -> Org:
        return await self._one_or_raise(
            Org,
            "update public.orgs set minutes_used = minutes_used + $2 where id = $1 returning *",
            org_id,
            minutes,
        )

    async def remaining_minutes(self, org_id: UUID) -> Decimal:
        value = await self.db.fetchval(
            "select minutes_quota - minutes_used from public.orgs where id = $1", org_id
        )
        if value is None:
            raise NotFoundError("Org")
        return Decimal(value)


# -------------------------------------------------------------- projects ----


class ProjectRepo(_Repo):
    async def get(self, project_id: UUID) -> Project | None:
        return await self._one(Project, "select * from public.projects where id = $1", project_id)

    async def get_for_org(self, org_id: UUID, project_id: UUID) -> Project | None:
        """The project, only if `org_id` owns it or has channel-partner access."""
        return await self._one(
            Project,
            """select p.* from public.projects p
               where p.id = $2
                 and (p.org_id = $1 or exists (
                   select 1 from public.project_access pa
                   where pa.project_id = p.id and pa.org_id = $1))""",
            org_id,
            project_id,
        )

    async def list_for_org(self, org_id: UUID, *, active_only: bool = True) -> list[Project]:
        return await self._many(
            Project,
            """select p.* from public.projects p
               where (p.org_id = $1 or exists (
                   select 1 from public.project_access pa
                   where pa.project_id = p.id and pa.org_id = $1))
                 and (not $2 or p.is_active)
               order by p.name""",
            org_id,
            active_only,
        )

    async def has_access(self, org_id: UUID, project_id: UUID) -> bool:
        return bool(
            await self.db.fetchval(
                """select exists (select 1 from public.projects where id = $2 and org_id = $1)
                       or exists (select 1 from public.project_access
                                  where project_id = $2 and org_id = $1)""",
                org_id,
                project_id,
            )
        )

    async def grant_access(self, project_id: UUID, org_id: UUID) -> None:
        await self.db.execute(
            """insert into public.project_access (project_id, org_id) values ($1, $2)
               on conflict do nothing""",
            project_id,
            org_id,
        )


class VisitSlotRepo(_Repo):
    async def list_for_project(self, project_id: UUID) -> list[VisitSlot]:
        return await self._many(
            VisitSlot,
            """select * from public.visit_slots where project_id = $1
               order by day_of_week, start_time""",
            project_id,
        )


# ------------------------------------------------------------- campaigns ----


class CampaignRepo(_Repo):
    async def get(self, org_id: UUID, campaign_id: UUID) -> Campaign | None:
        return await self._one(
            Campaign,
            "select * from public.campaigns where id = $2 and org_id = $1",
            org_id,
            campaign_id,
        )

    async def list_active(self) -> list[Campaign]:
        """All orgs' active campaigns (dialer scheduler)."""
        return await self._many(
            Campaign, "select * from public.campaigns where status = 'active' order by created_at"
        )

    async def set_status(self, org_id: UUID, campaign_id: UUID, status: CampaignStatus) -> Campaign:
        return await self._one_or_raise(
            Campaign,
            "update public.campaigns set status = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            campaign_id,
            status,
        )


# ----------------------------------------------------------------- leads ----


class LeadRepo(_Repo):
    async def upsert(self, lead: LeadCreate) -> Lead:
        """Insert, or on duplicate (org, project, phone) refresh name/lang/fields."""
        if lead.project_id is not None and not await ProjectRepo(self.db).has_access(
            lead.org_id, lead.project_id
        ):
            raise AccessDeniedError(f"org has no access to project {lead.project_id}")
        return await self._one_or_raise(
            Lead,
            """insert into public.leads
                 (org_id, project_id, campaign_id, name, phone, source, language_pref, fields)
               values ($1, $2, $3, $4, $5, $6, $7, $8)
               on conflict (org_id, project_id, phone) do update set
                 name          = coalesce(excluded.name, leads.name),
                 campaign_id   = coalesce(excluded.campaign_id, leads.campaign_id),
                 language_pref = coalesce(excluded.language_pref, leads.language_pref),
                 fields        = leads.fields || excluded.fields
               returning *""",
            lead.org_id,
            lead.project_id,
            lead.campaign_id,
            lead.name,
            lead.phone,
            lead.source,
            lead.language_pref,
            lead.fields.model_dump(exclude_none=True),
        )

    async def get(self, org_id: UUID, lead_id: UUID) -> Lead | None:
        return await self._one(
            Lead, "select * from public.leads where id = $2 and org_id = $1", org_id, lead_id
        )

    async def find_by_phone(self, phone: str, org_id: UUID | None = None) -> list[Lead]:
        """Inbound call routing: all leads with this number (optionally one org)."""
        return await self._many(
            Lead,
            """select * from public.leads where phone = $1 and ($2::uuid is null or org_id = $2)
               order by updated_at desc""",
            phone,
            org_id,
        )

    async def list_by_status(
        self, org_id: UUID, status: LeadStatus, *, limit: int = 100, offset: int = 0
    ) -> list[Lead]:
        return await self._many(
            Lead,
            """select * from public.leads where org_id = $1 and status = $2
               order by created_at desc limit $3 offset $4""",
            org_id,
            status,
            limit,
            offset,
        )

    async def list_dialable(
        self, org_id: UUID, campaign_id: UUID, *, max_attempts: int, now: datetime, limit: int
    ) -> list[Lead]:
        """Leads in a campaign that are due, under the attempt cap, and not on any DNC list."""
        return await self._many(
            Lead,
            """select l.* from public.leads l
               where l.org_id = $1 and l.campaign_id = $2
                 and l.status in ('new', 'queued', 'callback')
                 and l.attempt_count < $3
                 and (l.next_attempt_at is null or l.next_attempt_at <= $4)
                 and not exists (
                   select 1 from public.dnc d
                   where d.phone = l.phone and (d.org_id is null or d.org_id = l.org_id))
               order by l.next_attempt_at nulls first, l.created_at
               limit $5""",
            org_id,
            campaign_id,
            max_attempts,
            now,
            limit,
        )

    async def set_status(self, org_id: UUID, lead_id: UUID, status: LeadStatus) -> Lead:
        return await self._one_or_raise(
            Lead,
            "update public.leads set status = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            lead_id,
            status,
        )

    async def record_attempt(
        self, org_id: UUID, lead_id: UUID, *, at: datetime, next_attempt_at: datetime | None
    ) -> Lead:
        return await self._one_or_raise(
            Lead,
            """update public.leads set
                 attempt_count = attempt_count + 1,
                 last_attempt_at = $3,
                 next_attempt_at = $4
               where id = $2 and org_id = $1 returning *""",
            org_id,
            lead_id,
            at,
            next_attempt_at,
        )

    async def apply_post_call(
        self, org_id: UUID, lead_id: UUID, result: PostCallResult, status: LeadStatus
    ) -> Lead:
        return await self._one_or_raise(
            Lead,
            """update public.leads set
                 score = $3, score_reason = $4, fields = fields || $5, status = $6
               where id = $2 and org_id = $1 returning *""",
            org_id,
            lead_id,
            result.score,
            result.score_reason,
            result.fields.model_dump(exclude_none=True),
            status,
        )

    async def merge_fields(self, org_id: UUID, lead_id: UUID, fields: LeadFields) -> Lead:
        return await self._one_or_raise(
            Lead,
            "update public.leads set fields = fields || $3 where id = $2 and org_id = $1 returning *",
            org_id,
            lead_id,
            fields.model_dump(exclude_none=True),
        )


# ----------------------------------------------------------------- calls ----


class CallRepo(_Repo):
    async def create(self, call: CallCreate) -> Call:
        return await self._one_or_raise(
            Call,
            """insert into public.calls (org_id, lead_id, campaign_id, direction, provider,
                                         provider_call_id, status, language, metadata, started_at)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
               returning *""",
            call.org_id,
            call.lead_id,
            call.campaign_id,
            call.direction,
            call.provider,
            call.provider_call_id,
            call.status,
            call.language,
            call.metadata,
        )

    async def get(self, org_id: UUID, call_id: UUID) -> Call | None:
        return await self._one(
            Call, "select * from public.calls where id = $2 and org_id = $1", org_id, call_id
        )

    async def get_by_provider_id(self, provider: str, provider_call_id: str) -> Call | None:
        """Webhook lookup; the webhook doesn't know the org yet."""
        return await self._one(
            Call,
            "select * from public.calls where provider = $1 and provider_call_id = $2",
            provider,
            provider_call_id,
        )

    async def set_provider_call_id(
        self, org_id: UUID, call_id: UUID, provider_call_id: str
    ) -> Call:
        return await self._one_or_raise(
            Call,
            """update public.calls set provider_call_id = $3
               where id = $2 and org_id = $1 returning *""",
            org_id,
            call_id,
            provider_call_id,
        )

    async def mark_answered(self, org_id: UUID, call_id: UUID, *, at: datetime) -> Call:
        return await self._one_or_raise(
            Call,
            """update public.calls set status = 'in_progress', answered_at = $3
               where id = $2 and org_id = $1 returning *""",
            org_id,
            call_id,
            at,
        )

    async def mark_ended(
        self,
        org_id: UUID,
        call_id: UUID,
        *,
        status: CallStatus,
        ended_at: datetime,
        duration_s: int | None,
        hangup_cause: str | None = None,
    ) -> Call:
        return await self._one_or_raise(
            Call,
            """update public.calls set status = $3, ended_at = $4, duration_s = $5, hangup_cause = $6
               where id = $2 and org_id = $1 returning *""",
            org_id,
            call_id,
            status,
            ended_at,
            duration_s,
            hangup_cause,
        )

    async def save_transcript(
        self, org_id: UUID, call_id: UUID, transcript: list[dict[str, Any]]
    ) -> Call:
        return await self._one_or_raise(
            Call,
            "update public.calls set transcript = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            call_id,
            transcript,
        )

    async def save_post_call(
        self,
        org_id: UUID,
        call_id: UUID,
        result: PostCallResult,
        *,
        recording_url: str | None,
        cost_estimate: Decimal | None,
    ) -> Call:
        return await self._one_or_raise(
            Call,
            """update public.calls set
                 summary = $3, sentiment = $4, objections = $5, outcome = $6, next_action = $7,
                 recording_url = coalesce($8, recording_url), cost_estimate = $9
               where id = $2 and org_id = $1 returning *""",
            org_id,
            call_id,
            result.summary,
            result.sentiment,
            result.objections,
            result.outcome,
            result.next_action,
            recording_url,
            cost_estimate,
        )

    async def list_for_lead(self, org_id: UUID, lead_id: UUID) -> list[Call]:
        return await self._many(
            Call,
            """select * from public.calls where org_id = $1 and lead_id = $2
               order by started_at desc nulls last""",
            org_id,
            lead_id,
        )


# ------------------------------------------------------------- callbacks ----


class CallbackRepo(_Repo):
    async def create(
        self,
        org_id: UUID,
        lead_id: UUID,
        scheduled_at: datetime,
        *,
        reason: str | None = None,
        call_id: UUID | None = None,
    ) -> Callback:
        return await self._one_or_raise(
            Callback,
            """insert into public.callbacks (org_id, lead_id, call_id, scheduled_at, reason)
               values ($1, $2, $3, $4, $5) returning *""",
            org_id,
            lead_id,
            call_id,
            scheduled_at,
            reason,
        )

    async def list_due(self, before: datetime, *, limit: int = 100) -> list[Callback]:
        """Pending callbacks due by `before`, across orgs (worker)."""
        return await self._many(
            Callback,
            """select * from public.callbacks where status = 'pending' and scheduled_at <= $1
               order by scheduled_at limit $2""",
            before,
            limit,
        )

    async def set_status(self, org_id: UUID, callback_id: UUID, status: CallbackStatus) -> Callback:
        return await self._one_or_raise(
            Callback,
            "update public.callbacks set status = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            callback_id,
            status,
        )


# ----------------------------------------------------------- site_visits ----


class SiteVisitRepo(_Repo):
    async def book(
        self,
        org_id: UUID,
        lead_id: UUID,
        project_id: UUID,
        visit_slot_id: UUID,
        slot_start: datetime,
        slot_end: datetime,
        *,
        tz: str = DEFAULT_TZ,
    ) -> SiteVisit:
        """Book a visit inside a recurring slot, enforcing the slot's capacity.

        The slot row is locked FOR UPDATE so concurrent bookings can't oversell it.
        """
        async with transaction(self.db) as conn:
            if not await ProjectRepo(conn).has_access(org_id, project_id):
                raise AccessDeniedError(f"org has no access to project {project_id}")
            slot = await conn.fetchrow(
                """select * from public.visit_slots
                   where id = $1 and project_id = $2
                     and day_of_week = extract(isodow from ($3::timestamptz at time zone $5))
                     and ($3::timestamptz at time zone $5)::time >= start_time
                     and ($4::timestamptz at time zone $5)::time <= end_time
                     and ($3::timestamptz at time zone $5)::date = ($4::timestamptz at time zone $5)::date
                   for update""",
                visit_slot_id,
                project_id,
                slot_start,
                slot_end,
                tz,
            )
            if slot is None:
                raise SlotUnavailableError("time is outside the visit slot")
            taken = await conn.fetchval(
                """select count(*) from public.site_visits
                   where visit_slot_id = $1 and status in ('booked', 'confirmed')
                     and (slot_start at time zone $3)::date = ($2::timestamptz at time zone $3)::date""",
                visit_slot_id,
                slot_start,
                tz,
            )
            if taken >= slot["capacity"]:
                raise SlotUnavailableError("slot is full")
            row = await conn.fetchrow(
                """insert into public.site_visits
                     (org_id, lead_id, project_id, visit_slot_id, slot_start, slot_end)
                   values ($1, $2, $3, $4, $5, $6) returning *""",
                org_id,
                lead_id,
                project_id,
                visit_slot_id,
                slot_start,
                slot_end,
            )
            return SiteVisit.model_validate(dict(row))

    async def set_status(self, org_id: UUID, visit_id: UUID, status: VisitStatus) -> SiteVisit:
        return await self._one_or_raise(
            SiteVisit,
            "update public.site_visits set status = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            visit_id,
            status,
        )

    async def add_reminder(
        self, org_id: UUID, visit_id: UUID, reminder: dict[str, Any]
    ) -> SiteVisit:
        return await self._one_or_raise(
            SiteVisit,
            """update public.site_visits set reminders_sent = reminders_sent || jsonb_build_array($3::jsonb)
               where id = $2 and org_id = $1 returning *""",
            org_id,
            visit_id,
            reminder,
        )

    async def list_upcoming(self, after: datetime, before: datetime) -> list[SiteVisit]:
        """Booked/confirmed visits in a window, across orgs (reminder worker)."""
        return await self._many(
            SiteVisit,
            """select * from public.site_visits
               where status in ('booked', 'confirmed') and slot_start >= $1 and slot_start < $2
               order by slot_start""",
            after,
            before,
        )


# ----------------------------------------------------------- wa_messages ----


class WaMessageRepo(_Repo):
    async def create(
        self,
        org_id: UUID,
        lead_id: UUID,
        direction: Direction,
        type: WaMessageType,
        body: dict[str, Any],
        *,
        template_name: str | None = None,
        status: WaStatus = WaStatus.QUEUED,
        wa_message_id: str | None = None,
    ) -> WaMessage:
        return await self._one_or_raise(
            WaMessage,
            """insert into public.wa_messages
                 (org_id, lead_id, direction, type, template_name, body, status, wa_message_id)
               values ($1, $2, $3, $4, $5, $6, $7, $8) returning *""",
            org_id,
            lead_id,
            direction,
            type,
            template_name,
            body,
            status,
            wa_message_id,
        )

    async def set_wa_message_id(self, message_id: UUID, wa_message_id: str) -> WaMessage:
        return await self._one_or_raise(
            WaMessage,
            """update public.wa_messages set wa_message_id = $2, status = 'sent'
               where id = $1 returning *""",
            message_id,
            wa_message_id,
        )

    async def update_status(
        self, wa_message_id: str, status: WaStatus, *, error: str | None = None
    ) -> WaMessage | None:
        """Meta status webhook; keyed by Meta's message id."""
        return await self._one(
            WaMessage,
            """update public.wa_messages set status = $2, error = coalesce($3, error)
               where wa_message_id = $1 returning *""",
            wa_message_id,
            status,
            error,
        )


# ------------------------------------------------------------------- dnc ----


class DncRepo(_Repo):
    async def is_blocked(self, org_id: UUID, phone: str) -> bool:
        """True if the number is on this org's list or the global list."""
        return bool(
            await self.db.fetchval(
                """select exists (select 1 from public.dnc
                                  where phone = $2 and (org_id is null or org_id = $1))""",
                org_id,
                phone,
            )
        )

    async def add(self, org_id: UUID | None, phone: str, reason: str | None = None) -> DncEntry:
        return await self._one_or_raise(
            DncEntry,
            """insert into public.dnc (org_id, phone, reason) values ($1, $2, $3)
               on conflict (org_id, phone) do update set reason = coalesce(excluded.reason, dnc.reason)
               returning *""",
            org_id,
            phone,
            reason,
        )


# -------------------------------------------------------------- handoffs ----


class HandoffRepo(_Repo):
    async def create(self, org_id: UUID, call_id: UUID, agent_phone: str) -> Handoff:
        return await self._one_or_raise(
            Handoff,
            """insert into public.handoffs (org_id, call_id, agent_phone) values ($1, $2, $3)
               returning *""",
            org_id,
            call_id,
            agent_phone,
        )

    async def set_status(self, org_id: UUID, handoff_id: UUID, status: HandoffStatus) -> Handoff:
        return await self._one_or_raise(
            Handoff,
            "update public.handoffs set status = $3 where id = $2 and org_id = $1 returning *",
            org_id,
            handoff_id,
            status,
        )


# ---------------------------------------------------------- usage_events ----


class UsageRepo(_Repo):
    async def record(
        self,
        org_id: UUID,
        kind: UsageKind,
        qty: Decimal,
        cost: Decimal,
        *,
        call_id: UUID | None = None,
    ) -> UsageEvent:
        return await self._one_or_raise(
            UsageEvent,
            """insert into public.usage_events (org_id, call_id, kind, qty, cost)
               values ($1, $2, $3, $4, $5) returning *""",
            org_id,
            call_id,
            kind,
            qty,
            cost,
        )

    async def call_cost(self, org_id: UUID, call_id: UUID) -> Decimal:
        value = await self.db.fetchval(
            """select coalesce(sum(cost), 0) from public.usage_events
               where org_id = $1 and call_id = $2""",
            org_id,
            call_id,
        )
        return Decimal(value)
