import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.infra.db import close_db, conversations, get_db_conn, init_db


@pytest.mark.asyncio
async def test_database_atomicity():
    """DB 트랜잭션의 원자성(Atomicity)을 검증합니다.
    예외 발생 시 데이터가 롤백되어야 합니다.
    """
    # SQLite 인메모리 DB 또는 테스트 DB URL (기존 테스트 설정을 따름)
    db_url = "sqlite+aiosqlite:///:memory:"
    await init_db(db_url)

    user_id = "test_atomicity_user"

    try:
        async with get_db_conn() as conn:
            # 1. 첫 번째 데이터 삽입
            await conn.execute(
                conversations.insert().values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    messages=[{"role": "user", "content": "hello"}],
                    created_at=datetime.now(timezone.utc)
                )
            )

            # 2. 의도적인 예외 발생
            raise RuntimeError("Intentional failure for atomicity test")

    except RuntimeError:
        # 예외를 캐치하여 롤백이 되었는지 확인 준비
        pass

    # 3. DB 확인: 데이터가 없어야 함
    async with get_db_conn() as conn:
        query = select(conversations).where(conversations.c.user_id == user_id)
        result = await conn.execute(query)
        rows = result.mappings().all()

        # 원자성이 보장된다면 데이터가 0개여야 함
        assert len(rows) == 0, "Transaction should have been rolled back"

    await close_db()
