-- 외부 PostgreSQL/Supabase의 SQL Editor에서 한 번 실행합니다.
-- 웹 클라이언트가 아닌 Streamlit 서버가 전용 DB 연결로 접근합니다.
CREATE TABLE IF NOT EXISTS public.saved_games (
    id TEXT NOT NULL,
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (id, owner)
);
CREATE INDEX IF NOT EXISTS saved_games_owner_created ON public.saved_games(owner, created_at DESC);
ALTER TABLE public.saved_games ENABLE ROW LEVEL SECURITY;
-- 공개 anon/authenticated API에는 정책을 열지 않습니다.
-- DATABASE_URL에는 이 테이블에 접근 가능한 서버 전용 DB 계정을 사용합니다.
