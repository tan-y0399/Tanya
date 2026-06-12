import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings


async def main() -> int:
    from app.core.config import settings
    url = settings.database_url
    print(f"Connecting: {url.split('@')[-1]}")
    connect_args = {}
    if "postgresql" in url:
        connect_args["ssl"] = False
    eng = create_async_engine(url, connect_args=connect_args)
    try:
        async with eng.connect() as conn:
            r = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            )
            tables = [row[0] for row in r]
            print("OK tables:", tables)
            return 0
    except Exception as e:
        print(f"FAILED: {e}")
        return 1
    finally:
        await eng.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
