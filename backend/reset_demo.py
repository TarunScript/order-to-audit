#!/usr/bin/env python3
"""CLI Command: Reset demo database and reload Section 10 seed data."""
import asyncio
import sys
from sqlalchemy import text
from app.core.database import async_engine, Base
from seed import seed_data


async def reset_demo():
    print("🔄 Resetting Order-to-Audit database to PRD Section 10 initial state...")
    async with async_engine.begin() as conn:
        # Disable triggers and drop tables if needed, or recreate all tables
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables dropped and recreated.")

    print("🌱 Loading initial seed data (users, items, boms, customers, opening ledger)...")
    await seed_data()
    print("✅ Reset complete! Benchmark demo data is loaded and ready.")


if __name__ == "__main__":
    asyncio.run(reset_demo())
