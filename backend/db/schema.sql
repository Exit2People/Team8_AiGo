-- 회원 (F01 · F02 · F03). ERD v0.2 의 users · consents · sessions 와 같은 모양이에요.
-- 남기는 것: 카카오 회원 번호 또는 이메일 · 비밀번호 해시, 내 정보에 적은 이름 · 닉네임 · 나이, 거주지(동 ID), 동의 기록, 로그인 토큰의 해시. 전화 · 카카오 토큰은 남기지 않아요.
-- 동 ID 는 화면이 쓰는 frontend/lib/dongs.json 의 ID 예요(ERD 의 dongs 테이블은 아직 없어서 FK 는 걸지 않아요).
-- ERD 는 거주지 1안을 필수로 했지만, 가입 디자인(01-3)에 거주지 입력이 없어서 지금은 비워 둘 수 있어요.
create table if not exists users (
  id            uuid        primary key default gen_random_uuid(),
  kakao_id      text        unique,            -- 카카오로 가입한 사람
  email         text        unique,            -- 이메일로 가입한 사람
  password_hash text,                          -- scrypt 해시만(비밀번호 자체는 저장하지 않아요)
  name          text,                          -- 내 정보에 적은 이름 · 닉네임 · 나이(2026-11-19 결정: 보이게)
  nickname      text,
  age           smallint,
  home_dong1_id text,
  home_dong2_id text,
  created_at    timestamptz not null default now(),
  last_login_at timestamptz not null default now()
);

create table if not exists consents (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        not null references users (id) on delete cascade,
  doc_type    text        not null,
  doc_version text        not null,
  agreed_at   timestamptz not null default now()
);

create table if not exists sessions (
  id         text        primary key,  -- 세션 토큰의 해시(sha256). 토큰 자체는 저장하지 않아요
  user_id    uuid        not null references users (id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists sessions_user on sessions (user_id);

-- 이메일 가입 확인 숫자(10분, 5번까지). 숫자 · 비밀번호는 해시로만 둬요. 가입이 끝나면 지워요
create table if not exists email_codes (
  email         text        primary key,
  code_hash     text        not null,
  password_hash text        not null,
  expires_at    timestamptz not null,
  tries         int         not null default 0,
  verified      boolean     not null default false
);

-- AI GO 익명 소셜 기능 (로그인 없이 쓰는 M1). PostgreSQL (Neon).
-- 사람을 알아볼 값은 저장하지 않아요. client 는 기기가 만든 무작위 표시, nick 은 화면이 붙인 별명이에요.
-- 톡방 · 예정 인원은 하루 단위(day, 서울 날짜)예요. 지난 날의 톡방은 서버가 지워요.
-- 실행: psql "$DATABASE_URL" -f db/schema.sql  (여러 번 실행해도 돼요)

create table if not exists place_expects (
  day        date        not null,
  place_id   text        not null,
  client     text        not null,
  created_at timestamptz not null default now(),
  primary key (day, place_id, client)
);

create table if not exists chat_members (
  day       date        not null,
  place_id  text        not null,
  client    text        not null,
  nick      text        not null,
  joined_at timestamptz not null default now(),
  primary key (day, place_id, client)
);

create table if not exists chat_messages (
  id         bigint generated always as identity primary key,
  day        date        not null,
  place_id   text        not null,
  client     text        not null,
  nick       text        not null,
  kind       text        not null check (kind in ('system', 'text', 'quick')),
  body       text        not null,
  created_at timestamptz not null default now()
);
create index if not exists chat_messages_room on chat_messages (day, place_id, id);

-- 누가 신고했는지는 남기지 않아요
create table if not exists chat_reports (
  id          bigint generated always as identity primary key,
  day         date        not null,
  place_id    text        not null,
  target_nick text        not null,
  created_at  timestamptz not null default now()
);

create table if not exists place_reviews (
  id         bigint generated always as identity primary key,
  place_id   text        not null,
  nick       text        not null,
  tag        text        not null,
  body       text        not null,
  created_at timestamptz not null default now()
);
create index if not exists place_reviews_place on place_reviews (place_id, created_at desc);

-- 담고 달리기 랭킹 (docs/15_게임랭킹_DB연결.md). 회원마다 최고 기록 한 줄. 닉네임은 users 에서 읽어요(여기 두지 않아요)
-- 계정을 지우면 랭킹에서도 사라져요(on delete cascade)
create table if not exists game_scores (
  user_id     uuid        primary key references users (id) on delete cascade,
  steps       integer     not null check (steps between 0 and 999999),
  achieved_at timestamptz not null default now()  -- 최고 기록을 세운 때 (같은 걸음이면 먼저 세운 사람이 위)
);
create index if not exists game_scores_rank on game_scores (steps desc, achieved_at asc);

-- 탈퇴 후 3개월 보관 · 밴 (2026-11-20). 여러 번 실행해도 돼요
-- deleted_at: 탈퇴한 때(있으면 로그인 · 조회에서 빠져요) · purge_after: 이때가 지나면 완전히 지워요(cascade)
-- banned_at · banned_reason: 운영자가 SQL 로 표시해요. 로그인 · 가입 · 되살리기를 막아요
--   예) update users set banned_at = now(), banned_reason = '톡방 성희롱 신고' where email = '...';
alter table users add column if not exists deleted_at    timestamptz;
alter table users add column if not exists purge_after   timestamptz;
alter table users add column if not exists banned_at     timestamptz;
alter table users add column if not exists banned_reason text;
create index if not exists users_purge on users (purge_after) where purge_after is not null;
