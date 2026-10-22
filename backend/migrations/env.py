import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event, pool

from app.db import get_db_path

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 이전 대상은 앱과 같은 DB 파일이다. 환경변수 TASKFLOW_DB 가 없으면 backend/taskflow.db (실제 DB)이다.
# 복사본으로 연습할 때는 TASKFLOW_DB 를 복사본 경로로 지정한다.
target_metadata = None  # autogenerate 를 쓰지 않는다. 리비전은 직접 쓴다.


def run_migrations_offline() -> None:
    raise SystemExit("offline(SQL 출력) 모드는 쓰지 않는다. 이전은 DB 에 직접 실행한다.")


def run_migrations_online() -> None:
    path = get_db_path()
    print(f"[alembic] 대상 DB: {path}", file=sys.stderr)
    engine = create_engine(f"sqlite:///{path.as_posix()}", poolclass=pool.NullPool)

    # pysqlite 는 DDL 을 트랜잭션 밖에서 실행한다. 직접 BEGIN 을 보내 DDL 도 한 트랜잭션에 넣고,
    # 리비전 하나가 실패하면 그 리비전의 변경이 모두 취소되게 한다.
    @event.listens_for(engine, "connect")
    def _manual_transactions(dbapi_connection, _):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transactional_ddl=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
