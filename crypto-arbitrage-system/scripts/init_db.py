#!/usr/bin/env python3
"""Initialize database schema"""
import asyncio
import asyncpg
import sys

async def init_db():
    try:
        conn = await asyncpg.connect(
            host='localhost',
            database='arbitrage',
            user='arbitrage_user',
            password='change_me_in_production'
        )
        
        with open('docker/postgres/init.sql') as f:
            sql = f.read()
        
        await conn.execute(sql)
        print("✅ Database initialized successfully")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_db())
