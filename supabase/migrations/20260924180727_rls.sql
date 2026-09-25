-- =============================================================================
-- Row Level Security.
--   * A user sees rows of orgs they belong to (org_members).
--   * A project is visible to its owner org AND to orgs granted via project_access
--     (channel-partner / broker mode). Leads/calls stay private to the org that owns them.
--   * Backend services (api/voice/worker) connect as the service role / postgres and
--     bypass RLS; the repository layer always scopes by org_id itself.
-- Helper functions live in a non-exposed `private` schema and are SECURITY DEFINER
-- so policies on org_members don't recurse into themselves.
-- =============================================================================

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.is_org_member(p_org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.org_members m
    where m.org_id = p_org_id and m.user_id = (select auth.uid())
  );
$$;

create or replace function private.has_org_role(p_org_id uuid, p_roles public.member_role[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.org_members m
    where m.org_id = p_org_id
      and m.user_id = (select auth.uid())
      and m.role = any (p_roles)
  );
$$;

create or replace function private.can_access_project(p_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.projects p
    join public.org_members m on m.org_id = p.org_id
    where p.id = p_project_id and m.user_id = (select auth.uid())
  ) or exists (
    select 1
    from public.project_access pa
    join public.org_members m on m.org_id = pa.org_id
    where pa.project_id = p_project_id and m.user_id = (select auth.uid())
  );
$$;

-- Manage a project (edit config, slots, grant access): owner/manager of the OWNING org.
create or replace function private.can_manage_project(p_project_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.projects p
    join public.org_members m on m.org_id = p.org_id
    where p.id = p_project_id
      and m.user_id = (select auth.uid())
      and m.role in ('owner', 'manager')
  );
$$;

revoke all on all functions in schema private from public;
grant execute on all functions in schema private to authenticated;

-- ------------------------------------------------------------ enable RLS ----
alter table public.orgs            enable row level security;
alter table public.org_members     enable row level security;
alter table public.projects        enable row level security;
alter table public.project_access  enable row level security;
alter table public.visit_slots     enable row level security;
alter table public.campaigns       enable row level security;
alter table public.leads           enable row level security;
alter table public.calls           enable row level security;
alter table public.callbacks       enable row level security;
alter table public.site_visits     enable row level security;
alter table public.wa_messages     enable row level security;
alter table public.dnc             enable row level security;
alter table public.handoffs        enable row level security;
alter table public.usage_events    enable row level security;

-- Nothing for anonymous visitors.
revoke all on all tables in schema public from anon;

-- ------------------------------------------------------------------ orgs ----
create policy orgs_select on public.orgs for select to authenticated
  using ((select private.is_org_member(id)));
create policy orgs_update on public.orgs for update to authenticated
  using ((select private.has_org_role(id, '{owner}')))
  with check ((select private.has_org_role(id, '{owner}')));
-- Org creation + quota changes go through the backend (service role).

-- ----------------------------------------------------------- org_members ----
create policy org_members_select on public.org_members for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy org_members_insert on public.org_members for insert to authenticated
  with check ((select private.has_org_role(org_id, '{owner}')));
create policy org_members_update on public.org_members for update to authenticated
  using ((select private.has_org_role(org_id, '{owner}')))
  with check ((select private.has_org_role(org_id, '{owner}')));
create policy org_members_delete on public.org_members for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner}')));

-- -------------------------------------------------------------- projects ----
create policy projects_select on public.projects for select to authenticated
  using ((select private.can_access_project(id)));
create policy projects_insert on public.projects for insert to authenticated
  with check ((select private.has_org_role(org_id, '{owner,manager}')));
create policy projects_update on public.projects for update to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')))
  with check ((select private.has_org_role(org_id, '{owner,manager}')));
create policy projects_delete on public.projects for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner}')));

-- -------------------------------------------------------- project_access ----
-- Visible to the grantee org and to the project's owning org. Only the owner org grants.
create policy project_access_select on public.project_access for select to authenticated
  using ((select private.is_org_member(org_id)) or (select private.can_manage_project(project_id)));
create policy project_access_insert on public.project_access for insert to authenticated
  with check ((select private.can_manage_project(project_id)));
create policy project_access_delete on public.project_access for delete to authenticated
  using ((select private.can_manage_project(project_id)));

-- ----------------------------------------------------------- visit_slots ----
create policy visit_slots_select on public.visit_slots for select to authenticated
  using ((select private.can_access_project(project_id)));
create policy visit_slots_insert on public.visit_slots for insert to authenticated
  with check ((select private.can_manage_project(project_id)));
create policy visit_slots_update on public.visit_slots for update to authenticated
  using ((select private.can_manage_project(project_id)))
  with check ((select private.can_manage_project(project_id)));
create policy visit_slots_delete on public.visit_slots for delete to authenticated
  using ((select private.can_manage_project(project_id)));

-- ------------------------------------------------------------- campaigns ----
create policy campaigns_select on public.campaigns for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy campaigns_insert on public.campaigns for insert to authenticated
  with check (
    (select private.has_org_role(org_id, '{owner,manager}'))
    and (select private.can_access_project(project_id))
  );
create policy campaigns_update on public.campaigns for update to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')))
  with check (
    (select private.has_org_role(org_id, '{owner,manager}'))
    and (select private.can_access_project(project_id))
  );
create policy campaigns_delete on public.campaigns for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')));

-- ----------------------------------------------------------------- leads ----
create policy leads_select on public.leads for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy leads_insert on public.leads for insert to authenticated
  with check (
    (select private.is_org_member(org_id))
    and (project_id is null or (select private.can_access_project(project_id)))
  );
create policy leads_update on public.leads for update to authenticated
  using ((select private.is_org_member(org_id)))
  with check (
    (select private.is_org_member(org_id))
    and (project_id is null or (select private.can_access_project(project_id)))
  );
create policy leads_delete on public.leads for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')));

-- ------------------------------------------------ backend-written tables ----
-- calls, wa_messages, handoffs, usage_events: dashboard reads only.
create policy calls_select on public.calls for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy wa_messages_select on public.wa_messages for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy handoffs_select on public.handoffs for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy usage_events_select on public.usage_events for select to authenticated
  using ((select private.is_org_member(org_id)));

-- ------------------------------------------------------------- callbacks ----
create policy callbacks_select on public.callbacks for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy callbacks_insert on public.callbacks for insert to authenticated
  with check ((select private.is_org_member(org_id)));
create policy callbacks_update on public.callbacks for update to authenticated
  using ((select private.is_org_member(org_id)))
  with check ((select private.is_org_member(org_id)));
create policy callbacks_delete on public.callbacks for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')));

-- ----------------------------------------------------------- site_visits ----
create policy site_visits_select on public.site_visits for select to authenticated
  using ((select private.is_org_member(org_id)));
create policy site_visits_insert on public.site_visits for insert to authenticated
  with check (
    (select private.is_org_member(org_id))
    and (select private.can_access_project(project_id))
  );
create policy site_visits_update on public.site_visits for update to authenticated
  using ((select private.is_org_member(org_id)))
  with check (
    (select private.is_org_member(org_id))
    and (select private.can_access_project(project_id))
  );
create policy site_visits_delete on public.site_visits for delete to authenticated
  using ((select private.has_org_role(org_id, '{owner,manager}')));

-- ------------------------------------------------------------------- dnc ----
-- Org-level entries only; the global list (org_id null) is backend-managed and not exposed.
create policy dnc_select on public.dnc for select to authenticated
  using (org_id is not null and (select private.is_org_member(org_id)));
create policy dnc_insert on public.dnc for insert to authenticated
  with check (org_id is not null and (select private.is_org_member(org_id)));
create policy dnc_delete on public.dnc for delete to authenticated
  using (org_id is not null and (select private.has_org_role(org_id, '{owner,manager}')));

-- -------------------------------------------------------------- storage -----
-- recordings: private; objects stored as <org_id>/<call_id>.mp3
-- project-media: public read (brochures / floor plans sent over WhatsApp); stored as <org_id>/<project_id>/...
insert into storage.buckets (id, name, public)
values ('recordings', 'recordings', false), ('project-media', 'project-media', true)
on conflict (id) do nothing;

create policy recordings_select on storage.objects for select to authenticated
  using (
    bucket_id = 'recordings'
    and exists (
      select 1 from public.org_members m
      where m.user_id = (select auth.uid())
        and m.org_id::text = (storage.foldername(name))[1]
    )
  );

create policy project_media_write on storage.objects for insert to authenticated
  with check (
    bucket_id = 'project-media'
    and exists (
      select 1 from public.org_members m
      where m.user_id = (select auth.uid())
        and m.role in ('owner', 'manager')
        and m.org_id::text = (storage.foldername(name))[1]
    )
  );
