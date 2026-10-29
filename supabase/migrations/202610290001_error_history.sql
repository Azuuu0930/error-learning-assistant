-- Apply once as the project owner. No raw logs are exposed by public APIs.
begin;
create schema if not exists error_archive;
revoke all on schema error_archive from public, anon, authenticated, service_role;

create table if not exists error_archive.entries (
    id uuid primary key,
    received_at timestamptz not null default now(),
    language text not null check (language in ('python','c','cpp')),
    log_redacted text not null check (char_length(log_redacted) between 1 and 100000),
    redaction_count integer not null check (redaction_count between 0 and 100000),
    truncated boolean not null,
    analysis_status text not null default 'pending'
      check (analysis_status in ('pending','recognized','unrecognized','failed','rejected')),
    error_type text not null default 'unknown',
    category text not null default 'unknown'
);
alter table error_archive.entries enable row level security;
revoke all on error_archive.entries from public, anon, authenticated, service_role;

create or replace function public.archive_error(
    p_id uuid, p_language text, p_log text, p_redactions integer, p_truncated boolean)
returns void
language plpgsql security definer set search_path = pg_catalog, error_archive
as $$
begin
    if p_id is null or substring(p_id::text,15,1) <> '4' then
        raise exception 'Invalid record ID';
    end if;
    insert into error_archive.entries(id,language,log_redacted,redaction_count,truncated)
      values(p_id,p_language,p_log,p_redactions,p_truncated)
      on conflict (id) do nothing;
end;
$$;

create or replace function public.complete_error(
    p_id uuid, p_status text, p_error_type text, p_category text)
returns void
language plpgsql security definer set search_path = pg_catalog, error_archive
as $$
begin
    if p_status is null or p_status not in ('recognized','unrecognized','failed','rejected')
       or p_error_type is null or p_error_type not in (
         'unknown','SyntaxError','IncompleteInputError','IndentationError','NameError','UnboundLocalError',
         'TypeError','ValueError','IndexError','KeyError','AttributeError','ModuleNotFoundError',
         'ImportError','FileNotFoundError','ZeroDivisionError','RecursionError','StopIteration',
         'AssertionError','RuntimeError','UnicodeDecodeError','CompilationError','LinkerError','SegmentationFault')
       or p_category is null or p_category not in (
         'unknown','syntax','indentation','variable','type','value','index','key','attribute','module',
         'import','file','arithmetic','recursion','iteration','assertion','runtime','encoding','compile','linker')
    then
        raise exception 'Invalid analysis metadata';
    end if;
    update error_archive.entries
       set analysis_status=p_status, error_type=p_error_type, category=p_category
     where id=p_id and analysis_status='pending';
end;
$$;

revoke all on function public.archive_error(uuid,text,text,integer,boolean) from public,anon,authenticated;
revoke all on function public.complete_error(uuid,text,text,text) from public,anon,authenticated;
grant execute on function public.archive_error(uuid,text,text,integer,boolean) to service_role;
grant execute on function public.complete_error(uuid,text,text,text) to service_role;
comment on table error_archive.entries is
 'Owner-only redacted error logs. No public or teacher read access. Do not add identifying metadata.';
commit;
