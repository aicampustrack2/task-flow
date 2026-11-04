"""backend/.env 의 DATABASE_URL 로 연결해 schema.sql 을 한 번 실행하고 테이블마다 주인 · RLS 상태를 출력한다.

psycopg 는 프로젝트 의존성에 넣지 않는다. 실행할 때만 --with 로 쓴다.
    uv run --with "psycopg[binary]" python backend/supabase/apply_schema.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE.parent / ".env"
SCHEMA_PATH = HERE / "schema.sql"
TABLES = ("users", "sessions", "tasks")


def read_database_url() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"{ENV_PATH} 가 없습니다.")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("backend/.env 에 DATABASE_URL 이 없습니다.")


def main() -> None:
    try:
        import psycopg
    except ImportError:
        sys.exit('psycopg 가 없습니다. uv run --with "psycopg[binary]" 로 실행하세요.')

    url = read_database_url()
    try:
        # 오류 메시지에 접속 문자열이 섞일 수 있어 종류만 출력한다.
        with psycopg.connect(url) as conn:
            conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            rows = conn.execute(
                "select tablename, tableowner, rowsecurity from pg_tables "
                "where schemaname = 'public' and tablename = any(%s)",
                (list(TABLES),),
            ).fetchall()
    except psycopg.Error as e:
        sys.exit(f"실패: {type(e).__name__}")

    found = {name: (owner, rls) for name, owner, rls in rows}
    for name in TABLES:
        if name in found:
            owner, rls = found[name]
            print(f"{name}  owner={owner}  rls={'on' if rls else 'off'}")
        else:
            print(f"{name}  없음")


if __name__ == "__main__":
    main()
