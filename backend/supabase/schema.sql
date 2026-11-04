-- backend/app/db.py 의 init_db 와 같은 테이블 셋. 날짜는 글자(text) 그대로 둔다.

create table if not exists users (
    id bigint generated always as identity primary key,
    username text not null unique,
    password_hash text
);
alter table users enable row level security;

create table if not exists sessions (
    id text primary key,
    user_id bigint not null references users(id),
    expires_at bigint not null
);
alter table sessions enable row level security;

create table if not exists tasks (
    id bigint generated always as identity primary key,
    title text not null,
    description text not null default '',
    status text not null,
    owner_id bigint not null references users(id),
    priority text not null default 'NORMAL',
    due_date text
);
create index if not exists idx_tasks_owner_id on tasks(owner_id);
alter table tasks enable row level security;
