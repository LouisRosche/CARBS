#!/usr/bin/env python3
"""
Analyze arbitrage opportunities
Based on statistical analysis methodology from Pole (2007)
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta
from decimal import Decimal

async def analyze_opportunities():
    """Comprehensive opportunity analysis"""
    
    conn = await asyncpg.connect(
        host='localhost',
        database='arbitrage',
        user='arbitrage_user',
        password='change_me_in_production'
    )
    
    print("\n" + "="*70)
    print("CRYPTO ARBITRAGE ANALYSIS REPORT")
    print("="*70)
    
    # Overall statistics
    stats = await conn.fetchrow("""
        SELECT 
            COUNT(*) as total_opportunities,
            AVG(spread_percent) as avg_spread,
            MAX(spread_percent) as max_spread,
            MIN(spread_percent) as min_spread,
            SUM(estimated_profit_after_fees) as total_potential_profit,
            MIN(detected_at) as first_detected,
            MAX(detected_at) as last_detected
        FROM opportunities
    """)
    
    print(f"\n📊 OVERALL STATISTICS")
    print(f"   Total Opportunities: {stats['total_opportunities']:,}")
    print(f"   Average Spread: {stats['avg_spread']:.3f}%")
    print(f"   Max Spread: {stats['max_spread']:.3f}%")
    print(f"   Min Spread: {stats['min_spread']:.3f}%")
    print(f"   Total Potential Profit: ${stats['total_potential_profit']:,.2f}")
    print(f"   Data Range: {stats['first_detected']} to {stats['last_detected']}")
    
    # Performance by symbol
    symbol_stats = await conn.fetch("""
        SELECT 
            symbol,
            COUNT(*) as count,
            AVG(spread_percent) as avg_spread,
            MAX(spread_percent) as max_spread,
            AVG(estimated_profit_after_fees) as avg_profit
        FROM opportunities
        GROUP BY symbol
        ORDER BY count DESC
    """)
    
    print(f"\n🎯 PERFORMANCE BY SYMBOL")
    print(f"{'Symbol':<12} {'Count':>8} {'Avg Spread':>12} {'Max Spread':>12} {'Avg Profit':>12}")
    print("-" * 70)
    for row in symbol_stats:
        print(f"{row['symbol']:<12} {row['count']:>8,} "
              f"{row['avg_spread']:>11.3f}% {row['max_spread']:>11.3f}% "
              f"${row['avg_profit']:>10.2f}")
    
    # Best exchange pairs
    pair_stats = await conn.fetch("""
        SELECT 
            buy_exchange,
            sell_exchange,
            symbol,
            COUNT(*) as count,
            AVG(spread_percent) as avg_spread
        FROM opportunities
        WHERE detected_at > NOW() - INTERVAL '7 days'
        GROUP BY buy_exchange, sell_exchange, symbol
        HAVING COUNT(*) >= 10
        ORDER BY avg_spread DESC
        LIMIT 10
    """)
    
    print(f"\n🔄 TOP EXCHANGE PAIRS (Last 7 Days, Min 10 opportunities)")
    print(f"{'Buy Exchange':<15} {'Sell Exchange':<15} {'Symbol':<12} {'Count':>8} {'Avg Spread':>12}")
    print("-" * 70)
    for row in pair_stats:
        print(f"{row['buy_exchange']:<15} {row['sell_exchange']:<15} "
              f"{row['symbol']:<12} {row['count']:>8,} {row['avg_spread']:>11.3f}%")
    
    # Hourly distribution
    hourly = await conn.fetch("""
        SELECT 
            EXTRACT(HOUR FROM detected_at) as hour,
            COUNT(*) as count,
            AVG(spread_percent) as avg_spread
        FROM opportunities
        WHERE detected_at > NOW() - INTERVAL '7 days'
        GROUP BY hour
        ORDER BY hour
    """)
    
    print(f"\n⏰ HOURLY DISTRIBUTION (Last 7 Days, UTC)")
    print(f"{'Hour':>6} {'Count':>8} {'Avg Spread':>12}")
    print("-" * 30)
    for row in hourly:
        bar = "█" * int(row['count'] / 10) if row['count'] > 0 else ""
        print(f"{int(row['hour']):>5}h {row['count']:>8,} {row['avg_spread']:>11.3f}% {bar}")
    
    # Recent opportunities
    recent = await conn.fetch("""
        SELECT 
            detected_at,
            symbol,
            buy_exchange,
            sell_exchange,
            spread_percent,
            estimated_profit_after_fees
        FROM opportunities
        ORDER BY detected_at DESC
        LIMIT 10
    """)
    
    print(f"\n🕐 RECENT OPPORTUNITIES (Last 10)")
    print(f"{'Time':<20} {'Symbol':<12} {'Buy':>10} {'Sell':>10} {'Spread':>10} {'Profit':>10}")
    print("-" * 80)
    for row in recent:
        print(f"{str(row['detected_at']):<20} {row['symbol']:<12} "
              f"{row['buy_exchange']:>10} {row['sell_exchange']:>10} "
              f"{row['spread_percent']:>9.3f}% ${row['estimated_profit_after_fees']:>8.2f}")
    
    print("\n" + "="*70)
    print("✅ Analysis complete!")
    print("="*70 + "\n")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_opportunities())
