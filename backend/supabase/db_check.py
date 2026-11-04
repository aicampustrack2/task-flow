"""backend/.env 의 DATABASE_URL 로 연결해 상태를 읽기만 한다. 비밀번호는 출력하지 않는다.

psycopg 는 프로젝트 의존성에 넣지 않는다. 실행할 때만 --with 로 쓴다.
    uv run --with "psycopg[binary]" python backend/supabase/db_check.py
"""
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
TABLES = ("users", "sessions", "tasks")
QUERY_RUNS = 5


def read_database_url() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"{ENV_PATH} 가 없습니다.")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("backend/.env 에 DATABASE_URL 이 없습니다.")


def describe_port(port: int | None) -> str:
    if port == 6543:
        return "6543 (pooler)"
    if port == 5432:
        return "5432 (direct)"
    return str(port)


def main() -> None:
    try:
        import psycopg
    except ImportError:
        sys.exit('psycopg 가 없습니다. uv run --with "psycopg[binary]" 로 실행하세요.')

    url = read_database_url()
    parsed = urlparse(url)  # 사용자 이름 · 비밀번호는 쓰지 않는다.
    host, port = parsed.hostname, parsed.port or 5432

    try:
        started = time.perf_counter()
        # 6543 은 트랜잭션 풀러라 서버 측 prepared statement 를 끈다.
        with psycopg.connect(url, prepare_threshold=None) as conn:
            connect_ms = (time.perf_counter() - started) * 1000
            conn.read_only = True  # 읽기만: 쓰기 명령은 서버가 거부한다.

            version = conn.execute("show server_version").fetchone()[0]
            role = conn.execute("select current_user").fetchone()[0]

            samples = []
            for _ in range(QUERY_RUNS):
                t = time.perf_counter()
                conn.execute("select 1").fetchone()
                samples.append((time.perf_counter() - t) * 1000)

            rows = conn.execute(
                "select tablename, tableowner, rowsecurity from pg_tables "
                "where schemaname = 'public' and tablename = any(%s)",
                (list(TABLES),),
            ).fetchall()
    except psycopg.Error as e:
        sys.exit(f"실패: {type(e).__name__}")

    print(f"① host={host}  port={describe_port(port)}  server=PostgreSQL {version}  role={role}")
    print(
        f"② connect={connect_ms:.0f} ms  "
        f"query(select 1 x{QUERY_RUNS}, median)={statistics.median(samples):.0f} ms"
    )
    found = {name: (owner, rls) for name, owner, rls in rows}
    parts = []
    for name in TABLES:
        if name in found:
            owner, rls = found[name]
            parts.append(f"{name} owner={owner} rls={'on' if rls else 'off'}")
        else:
            parts.append(f"{name} 없음")
    print("③ " + " | ".join(parts))


if __name__ == "__main__":
    main()
