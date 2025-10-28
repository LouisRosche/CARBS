# Utility Scripts

## init_db.py
Initialize PostgreSQL/TimescaleDB schema. Run after starting Docker containers.

```bash
python scripts/init_db.py
```

## analyze.py
Generate comprehensive analysis report of detected opportunities.

```bash
python scripts/analyze.py
```

Output includes:
- Overall statistics
- Performance by symbol
- Best exchange pairs
- Hourly distribution
- Recent opportunities
