-- Composite (child_id, org_id) FKs need covering indexes (Supabase advisor 0001).
-- Each replaces a single-column index whose leading column it keeps, so
-- lookups by lead_id / call_id / campaign_id are still served.

drop index if exists public.calls_lead_id_idx;
create index calls_lead_id_org_id_idx on public.calls (lead_id, org_id);

drop index if exists public.calls_campaign_id_idx;
create index calls_campaign_id_org_id_idx on public.calls (campaign_id, org_id);

drop index if exists public.leads_campaign_id_idx;
create index leads_campaign_id_org_id_idx on public.leads (campaign_id, org_id);

drop index if exists public.callbacks_lead_id_idx;
create index callbacks_lead_id_org_id_idx on public.callbacks (lead_id, org_id);

drop index if exists public.site_visits_lead_id_idx;
create index site_visits_lead_id_org_id_idx on public.site_visits (lead_id, org_id);

drop index if exists public.wa_messages_lead_id_idx;
create index wa_messages_lead_id_org_id_idx on public.wa_messages (lead_id, org_id, created_at desc);

drop index if exists public.handoffs_call_id_idx;
create index handoffs_call_id_org_id_idx on public.handoffs (call_id, org_id);
