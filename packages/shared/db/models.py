"""Pydantic models for rows in the core tables, plus typed views of the JSON columns.

Row models mirror columns 1:1 so `Model.model_validate(dict(record))` just works.
`*Create` models carry only what callers supply; the DB fills ids and timestamps.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from shared.db.enums import (
    CallbackStatus,
    CallOutcome,
    CallStatus,
    CampaignStatus,
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
    VisitStatus,
    WaMessageType,
    WaStatus,
)

E164 = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{7,14}$")]


class _Row(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------ JSON shapes ----


class Localized(BaseModel):
    """Text in every call language. English is the required fallback."""

    en: str
    hi: str | None = None
    mr: str | None = None

    def get(self, lang: LanguageCode | str) -> str:
        return getattr(self, str(lang), None) or self.en


class BhkType(BaseModel):
    type: str
    carpet_sqft: tuple[int, int]
    price_inr: tuple[int, int]


class Possession(BaseModel):
    target_date: date
    rera_date: date
    status: Literal["under_construction", "ready_to_move", "nearing_possession"]


class Landmark(BaseModel):
    name: str
    distance_km: float


class ProjectLocation(BaseModel):
    address: str
    map_url: str
    lat: float
    lng: float
    landmarks: list[Landmark] = Field(default_factory=list)


class ProjectMedia(BaseModel):
    brochure_url: str | None = None
    floor_plan_urls: list[str] = Field(default_factory=list)
    emi_calculator_url: str | None = None


class FaqItem(BaseModel):
    id: str
    q: Localized
    a: Localized


NextStep = Literal[
    "book_site_visit",
    "schedule_callback",
    "send_whatsapp_kit",
    "transfer_to_human",
    "mark_not_interested",
]


class Objection(BaseModel):
    key: str
    triggers: list[str] = Field(default_factory=list)
    response: Localized
    never_offer: list[str] = Field(default_factory=list)
    next_step: NextStep | None = None


class ProjectConfig(BaseModel):
    """`projects.config`. The only source of facts the bot may state on a call."""

    model_config = ConfigDict(extra="allow")

    company_display_name: Localized
    project_display_name: Localized
    tagline: str | None = None
    bhk_types: list[BhkType]
    price_note: str | None = None
    payment_plans: list[str] = Field(default_factory=list)
    amenities: list[str] = Field(default_factory=list)
    possession: Possession
    loan_partners: list[str] = Field(default_factory=list)
    location: ProjectLocation
    media: ProjectMedia = Field(default_factory=ProjectMedia)
    site_office_hours: str | None = None
    faq: list[FaqItem] = Field(default_factory=list)
    objections: list[Objection] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)


class LeadFields(BaseModel):
    """`leads.fields`: what qualification has captured so far."""

    model_config = ConfigDict(extra="allow")

    bhk: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    location_pref: str | None = None
    timeline: str | None = None
    loan_needed: bool | None = None
    purpose: Literal["live", "invest"] | None = None


class CallingWindow(BaseModel):
    start: time = time(9, 0)
    end: time = time(21, 0)
    days: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])  # ISO weekdays


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    retry_after_minutes: list[int] = Field(default_factory=lambda: [60, 240, 1440])


# ------------------------------------------------------------------- rows ----


class Org(_Row):
    id: UUID
    name: str
    type: OrgType
    plan: str
    minutes_quota: int
    minutes_used: Decimal
    created_at: datetime
    updated_at: datetime


class OrgMember(_Row):
    org_id: UUID
    user_id: UUID
    role: MemberRole
    created_at: datetime


class Project(_Row):
    id: UUID
    org_id: UUID
    builder_name: str
    name: str
    location: str
    rera_no: str | None
    config: ProjectConfig
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VisitSlot(_Row):
    id: UUID
    project_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    capacity: int
    created_at: datetime


class Campaign(_Row):
    id: UUID
    org_id: UUID
    project_id: UUID
    name: str
    status: CampaignStatus
    calling_window: CallingWindow
    max_concurrency: int
    retry_policy: RetryPolicy
    created_at: datetime
    updated_at: datetime


class LeadCreate(BaseModel):
    org_id: UUID
    project_id: UUID | None = None
    campaign_id: UUID | None = None
    name: str | None = None
    phone: E164
    source: LeadSource = LeadSource.CSV
    language_pref: LanguageCode | None = None
    fields: LeadFields = Field(default_factory=LeadFields)


class Lead(_Row):
    id: UUID
    org_id: UUID
    project_id: UUID | None
    campaign_id: UUID | None
    name: str | None
    phone: str
    source: LeadSource
    language_pref: LanguageCode | None
    status: LeadStatus
    score: LeadScore | None
    score_reason: str | None
    fields: LeadFields
    assigned_agent_id: UUID | None
    attempt_count: int
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CallCreate(BaseModel):
    org_id: UUID
    lead_id: UUID
    campaign_id: UUID | None = None
    direction: Direction
    provider: str = "plivo"
    provider_call_id: str | None = None
    status: CallStatus = CallStatus.QUEUED
    language: LanguageCode | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Call(_Row):
    id: UUID
    org_id: UUID
    lead_id: UUID
    campaign_id: UUID | None
    direction: Direction
    provider: str
    provider_call_id: str | None
    status: CallStatus
    language: LanguageCode | None
    started_at: datetime | None
    answered_at: datetime | None
    ended_at: datetime | None
    duration_s: int | None
    hangup_cause: str | None
    recording_url: str | None
    transcript: list[dict[str, Any]]
    summary: str | None
    sentiment: Sentiment | None
    objections: list[Any]
    outcome: CallOutcome | None
    next_action: str | None
    cost_estimate: Decimal | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PostCallResult(BaseModel):
    """Strict JSON the post-call LLM must return (see CLAUDE.md, Post-call job)."""

    summary: str
    score: LeadScore
    score_reason: str
    fields: LeadFields
    sentiment: Sentiment
    objections: list[str]
    outcome: CallOutcome
    next_action: str


class Callback(_Row):
    id: UUID
    org_id: UUID
    lead_id: UUID
    call_id: UUID | None
    scheduled_at: datetime
    reason: str | None
    status: CallbackStatus
    created_at: datetime
    updated_at: datetime


class SiteVisit(_Row):
    id: UUID
    org_id: UUID
    lead_id: UUID
    project_id: UUID
    visit_slot_id: UUID | None
    slot_start: datetime
    slot_end: datetime
    status: VisitStatus
    reminders_sent: list[Any]
    feedback: str | None
    created_at: datetime
    updated_at: datetime


class WaMessage(_Row):
    id: UUID
    org_id: UUID
    lead_id: UUID
    direction: Direction
    type: WaMessageType
    template_name: str | None
    body: dict[str, Any]
    status: WaStatus
    wa_message_id: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class DncEntry(_Row):
    id: UUID
    org_id: UUID | None
    phone: str
    reason: str | None
    added_at: datetime


class Handoff(_Row):
    id: UUID
    org_id: UUID
    call_id: UUID
    agent_phone: str
    status: HandoffStatus
    created_at: datetime
    updated_at: datetime


class UsageEvent(_Row):
    id: int
    org_id: UUID
    call_id: UUID | None
    kind: UsageKind
    qty: Decimal
    cost: Decimal
    created_at: datetime
