"""Python mirrors of the Postgres enums in supabase/migrations/*_core_schema.sql."""

from enum import StrEnum


class OrgType(StrEnum):
    BUILDER = "builder"
    BROKER = "broker"
    CHANNEL_PARTNER = "channel_partner"


class MemberRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    AGENT = "agent"


class LanguageCode(StrEnum):
    MR = "mr"
    HI = "hi"
    EN = "en"


class LeadSource(StrEnum):
    CSV = "csv"
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    PORTAL = "portal"
    WEBSITE = "website"
    INBOUND = "inbound"


class LeadStatus(StrEnum):
    NEW = "new"
    QUEUED = "queued"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    VISIT_BOOKED = "visit_booked"
    VISITED = "visited"
    CALLBACK = "callback"
    NOT_INTERESTED = "not_interested"
    DNC = "dnc"
    CONVERTED = "converted"
    INVALID = "invalid"


class LeadScore(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(StrEnum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"
    CANCELED = "canceled"


class CallOutcome(StrEnum):
    INTERESTED = "interested"
    VISIT_BOOKED = "visit_booked"
    CALLBACK_REQUESTED = "callback_requested"
    NOT_INTERESTED = "not_interested"
    DNC = "dnc"
    WRONG_NUMBER = "wrong_number"
    TRANSFERRED = "transferred"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    OTHER = "other"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class CallbackStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


class VisitStatus(StrEnum):
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    DONE = "done"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class WaMessageType(StrEnum):
    TEXT = "text"
    TEMPLATE = "template"
    DOCUMENT = "document"
    IMAGE = "image"
    LOCATION = "location"
    INTERACTIVE = "interactive"
    OTHER = "other"


class WaStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"


class HandoffStatus(StrEnum):
    PENDING = "pending"
    RINGING = "ringing"
    CONNECTED = "connected"
    FAILED = "failed"
    COMPLETED = "completed"


class UsageKind(StrEnum):
    CALL_MINUTE = "call_minute"
    WA_MESSAGE = "wa_message"
    TTS_CHARS = "tts_chars"
    STT_SECONDS = "stt_seconds"
    LLM_TOKENS = "llm_tokens"
