-- =============================================================================
-- PropCall core schema: enums, tables, constraints, indexes, updated_at triggers.
-- RLS policies live in the next migration.
-- Every tenant table carries org_id (denormalised on child tables) so RLS is a
-- single indexed lookup, and composite FKs keep child.org_id == parent.org_id.
-- =============================================================================


-- ----------------------------------------------------------------- enums ----
create type public.org_type          as enum ('builder', 'broker', 'channel_partner');
create type public.member_role       as enum ('owner', 'manager', 'agent');
create type public.language_code     as enum ('mr', 'hi', 'en');
create type public.lead_source       as enum ('csv', 'meta_ads', 'google_ads', 'portal', 'website', 'inbound');
create type public.lead_status       as enum (
  'new', 'queued', 'contacted', 'qualified', 'visit_booked', 'visited',
  'callback', 'not_interested', 'dnc', 'converted', 'invalid'
);
create type public.lead_score        as enum ('hot', 'warm', 'cold');
create type public.campaign_status   as enum ('draft', 'active', 'paused', 'completed', 'archived');
create type public.direction         as enum ('inbound', 'outbound');
create type public.call_status       as enum (
  'queued', 'ringing', 'in_progress', 'completed', 'no_answer', 'busy',
  'failed', 'voicemail', 'canceled'
);
create type public.call_outcome      as enum (
  'interested', 'visit_booked', 'callback_requested', 'not_interested', 'dnc',
  'wrong_number', 'transferred', 'no_answer', 'voicemail', 'other'
);
create type public.sentiment         as enum ('positive', 'neutral', 'negative');
create type public.callback_status   as enum ('pending', 'done', 'cancelled', 'failed');
create type public.visit_status      as enum ('booked', 'confirmed', 'done', 'no_show', 'cancelled');
create type public.wa_message_type   as enum ('text', 'template', 'document', 'image', 'location', 'interactive', 'other');
create type public.wa_status         as enum ('queued', 'sent', 'delivered', 'read', 'failed', 'received');
create type public.handoff_status    as enum ('pending', 'ringing', 'connected', 'failed', 'completed');
create type public.usage_kind        as enum ('call_minute', 'wa_message', 'tts_chars', 'stt_seconds', 'llm_tokens');

-- E.164: + then 8-15 digits, no leading zero
create domain public.e164 as text check (value ~ '^\+[1-9][0-9]{7,14}$');

-- --------------------------------------------------------- updated_at -------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ------------------------------------------------------------------ orgs ----
create table public.orgs (
  id             uuid primary key default gen_random_uuid(),
  name           text not null check (length(trim(name)) > 0),
  type           public.org_type not null,
  plan           text not null default 'pilot',
  minutes_quota  integer not null default 0 check (minutes_quota >= 0),
  minutes_used   numeric(12, 2) not null default 0 check (minutes_used >= 0),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table public.org_members (
  org_id      uuid not null references public.orgs (id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  role        public.member_role not null default 'agent',
  created_at  timestamptz not null default now(),
  primary key (org_id, user_id)
);
create index org_members_user_id_idx on public.org_members (user_id);

-- -------------------------------------------------------------- projects ----
create table public.projects (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null references public.orgs (id) on delete cascade,
  builder_name  text not null,
  name          text not null,
  location      text not null,
  rera_no       text,
  config        jsonb not null default '{}'::jsonb check (jsonb_typeof(config) = 'object'),
  is_active     boolean not null default true,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (org_id, name)
);
create index projects_org_id_idx on public.projects (org_id);

-- Channel-partner mode: org_id (a broker) may work leads for project_id (a builder's project).
create table public.project_access (
  project_id  uuid not null references public.projects (id) on delete cascade,
  org_id      uuid not null references public.orgs (id) on delete cascade,
  granted_at  timestamptz not null default now(),
  primary key (project_id, org_id)
);
create index project_access_org_id_idx on public.project_access (org_id);

create table public.visit_slots (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references public.projects (id) on delete cascade,
  day_of_week  smallint not null check (day_of_week between 1 and 7), -- ISO: 1=Mon .. 7=Sun
  start_time   time not null,
  end_time     time not null,
  capacity     integer not null default 5 check (capacity > 0),
  created_at   timestamptz not null default now(),
  check (end_time > start_time),
  unique (project_id, day_of_week, start_time)
);
create index visit_slots_project_id_idx on public.visit_slots (project_id);

-- ------------------------------------------------------------- campaigns ----
create table public.campaigns (
  id               uuid primary key default gen_random_uuid(),
  org_id           uuid not null references public.orgs (id) on delete cascade,
  project_id       uuid not null references public.projects (id) on delete restrict,
  name             text not null,
  status           public.campaign_status not null default 'draft',
  -- {"start":"10:00","end":"19:00","days":[1,2,3,4,5,6]}; can only narrow the global 09:00-21:00 IST
  calling_window   jsonb not null default '{"start":"09:00","end":"21:00","days":[1,2,3,4,5,6,7]}'::jsonb,
  max_concurrency  integer not null default 2 check (max_concurrency between 1 and 100),
  -- {"max_attempts":3,"retry_after_minutes":[60,240,1440]}
  retry_policy     jsonb not null default '{"max_attempts":3,"retry_after_minutes":[60,240,1440]}'::jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (id, org_id)
);
create index campaigns_org_id_status_idx on public.campaigns (org_id, status);
create index campaigns_project_id_idx on public.campaigns (project_id);

-- ----------------------------------------------------------------- leads ----
create table public.leads (
  id                 uuid primary key default gen_random_uuid(),
  org_id             uuid not null references public.orgs (id) on delete cascade,
  project_id         uuid references public.projects (id) on delete set null,
  campaign_id        uuid,
  name               text,
  phone              public.e164 not null,
  source             public.lead_source not null default 'csv',
  language_pref      public.language_code,
  status             public.lead_status not null default 'new',
  score              public.lead_score,
  score_reason       text,
  -- bhk, budget_min, budget_max, location_pref, timeline, loan_needed, purpose(live|invest)
  fields             jsonb not null default '{}'::jsonb check (jsonb_typeof(fields) = 'object'),
  assigned_agent_id  uuid references auth.users (id) on delete set null,
  attempt_count      integer not null default 0 check (attempt_count >= 0),
  last_attempt_at    timestamptz,
  next_attempt_at    timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (id, org_id),
  unique nulls not distinct (org_id, project_id, phone),
  foreign key (campaign_id, org_id) references public.campaigns (id, org_id) on delete set null (campaign_id)
);
create index leads_phone_idx on public.leads (phone);
create index leads_org_id_status_idx on public.leads (org_id, status);
create index leads_project_id_idx on public.leads (project_id);
create index leads_campaign_id_idx on public.leads (campaign_id);
create index leads_assigned_agent_id_idx on public.leads (assigned_agent_id);
create index leads_next_attempt_idx on public.leads (org_id, next_attempt_at) where next_attempt_at is not null;

-- ----------------------------------------------------------------- calls ----
create table public.calls (
  id                uuid primary key default gen_random_uuid(),
  org_id            uuid not null,
  lead_id           uuid not null,
  campaign_id       uuid,
  direction         public.direction not null,
  provider          text not null default 'plivo',
  provider_call_id  text,
  status            public.call_status not null default 'queued',
  language          public.language_code,
  started_at        timestamptz,
  answered_at       timestamptz,
  ended_at          timestamptz,
  duration_s        integer check (duration_s >= 0),
  hangup_cause      text,
  recording_url     text,
  transcript        jsonb not null default '[]'::jsonb check (jsonb_typeof(transcript) = 'array'),
  summary           text,
  sentiment         public.sentiment,
  objections        jsonb not null default '[]'::jsonb check (jsonb_typeof(objections) = 'array'),
  outcome           public.call_outcome,
  next_action       text,
  cost_estimate     numeric(10, 4),
  metadata          jsonb not null default '{}'::jsonb,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (id, org_id),
  unique (provider, provider_call_id),
  foreign key (lead_id, org_id) references public.leads (id, org_id) on delete cascade,
  foreign key (campaign_id, org_id) references public.campaigns (id, org_id) on delete set null (campaign_id)
);
create index calls_lead_id_idx on public.calls (lead_id);
create index calls_started_at_idx on public.calls (started_at desc);
create index calls_org_id_started_at_idx on public.calls (org_id, started_at desc);
create index calls_campaign_id_idx on public.calls (campaign_id);

-- ------------------------------------------------------------- callbacks ----
create table public.callbacks (
  id            uuid primary key default gen_random_uuid(),
  org_id        uuid not null,
  lead_id       uuid not null,
  call_id       uuid references public.calls (id) on delete set null,
  scheduled_at  timestamptz not null,
  reason        text,
  status        public.callback_status not null default 'pending',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  foreign key (lead_id, org_id) references public.leads (id, org_id) on delete cascade
);
create index callbacks_scheduled_at_idx on public.callbacks (scheduled_at) where status = 'pending';
create index callbacks_lead_id_idx on public.callbacks (lead_id);
create index callbacks_call_id_idx on public.callbacks (call_id);
create index callbacks_org_id_idx on public.callbacks (org_id);

-- ----------------------------------------------------------- site_visits ----
create table public.site_visits (
  id              uuid primary key default gen_random_uuid(),
  org_id          uuid not null,
  lead_id         uuid not null,
  project_id      uuid not null references public.projects (id) on delete restrict,
  visit_slot_id   uuid references public.visit_slots (id) on delete set null,
  slot_start      timestamptz not null,
  slot_end        timestamptz not null,
  status          public.visit_status not null default 'booked',
  reminders_sent  jsonb not null default '[]'::jsonb check (jsonb_typeof(reminders_sent) = 'array'),
  feedback        text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  check (slot_end > slot_start),
  foreign key (lead_id, org_id) references public.leads (id, org_id) on delete cascade
);
create index site_visits_slot_start_idx on public.site_visits (slot_start);
create index site_visits_project_slot_idx on public.site_visits (project_id, slot_start) where status in ('booked', 'confirmed');
create index site_visits_lead_id_idx on public.site_visits (lead_id);
create index site_visits_org_id_idx on public.site_visits (org_id);
create index site_visits_visit_slot_id_idx on public.site_visits (visit_slot_id);

-- ----------------------------------------------------------- wa_messages ----
create table public.wa_messages (
  id              uuid primary key default gen_random_uuid(),
  org_id          uuid not null,
  lead_id         uuid not null,
  direction       public.direction not null,
  type            public.wa_message_type not null default 'text',
  template_name   text,
  body            jsonb not null default '{}'::jsonb,
  status          public.wa_status not null default 'queued',
  wa_message_id   text unique,
  error           text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  foreign key (lead_id, org_id) references public.leads (id, org_id) on delete cascade
);
create index wa_messages_lead_id_idx on public.wa_messages (lead_id, created_at desc);
create index wa_messages_org_id_idx on public.wa_messages (org_id);

-- ------------------------------------------------------------------- dnc ----
create table public.dnc (
  id        uuid primary key default gen_random_uuid(),
  org_id    uuid references public.orgs (id) on delete cascade, -- null = global
  phone     public.e164 not null,
  reason    text,
  added_at  timestamptz not null default now(),
  unique nulls not distinct (org_id, phone)
);
create index dnc_phone_idx on public.dnc (phone);

-- -------------------------------------------------------------- handoffs ----
create table public.handoffs (
  id           uuid primary key default gen_random_uuid(),
  org_id       uuid not null,
  call_id      uuid not null,
  agent_phone  public.e164 not null,
  status       public.handoff_status not null default 'pending',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  foreign key (call_id, org_id) references public.calls (id, org_id) on delete cascade
);
create index handoffs_call_id_idx on public.handoffs (call_id);
create index handoffs_org_id_idx on public.handoffs (org_id);

-- ---------------------------------------------------------- usage_events ----
create table public.usage_events (
  id          bigint generated always as identity primary key,
  org_id      uuid not null references public.orgs (id) on delete cascade,
  call_id     uuid references public.calls (id) on delete set null,
  kind        public.usage_kind not null,
  qty         numeric(14, 4) not null check (qty >= 0),
  cost        numeric(12, 6) not null default 0,
  created_at  timestamptz not null default now()
);
create index usage_events_org_id_created_idx on public.usage_events (org_id, created_at desc);
create index usage_events_call_id_idx on public.usage_events (call_id);

-- ------------------------------------------------------ updated_at hooks ----
do $$
declare t text;
begin
  foreach t in array array[
    'orgs', 'projects', 'campaigns', 'leads', 'calls', 'callbacks',
    'site_visits', 'wa_messages', 'handoffs'
  ] loop
    execute format(
      'create trigger set_updated_at before update on public.%I
         for each row execute function public.set_updated_at()', t);
  end loop;
end;
$$;
