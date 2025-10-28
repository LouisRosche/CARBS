# Project Structure

```
crypto-arbitrage-system/
├── README.md                    # Main documentation
├── LICENSE                      # MIT License
├── requirements.txt            # Python dependencies
├── setup.py                    # Package configuration
├── Makefile                    # Common tasks
├── docker-compose.yml          # Infrastructure orchestration
├── pytest.ini                  # Test configuration
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
│
├── config/                     # Configuration
│   └── config.yaml            # Application settings
│
├── src/                        # Source code
│   ├── main.py                # Application entry point
│   ├── core/                  # Core arbitrage logic
│   │   ├── __init__.py
│   │   └── engine.py          # Main arbitrage engine
│   ├── config/                # Config management
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/              # Database layer
│   │   ├── __init__.py
│   │   └── connection.py
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── cache.py           # Redis cache
│       └── metrics.py         # Prometheus metrics
│
├── tests/                      # Test suite
│   ├── __init__.py
│   └── test_engine.py
│
├── scripts/                    # Utility scripts
│   ├── README.md
│   ├── init_db.py             # Database initialization
│   └── analyze.py             # Opportunity analysis
│
├── docker/                     # Docker configs
│   ├── postgres/
│   │   └── init.sql           # Database schema
│   ├── prometheus/
│   │   └── prometheus.yml     # Metrics config
│   └── grafana/
│       ├── dashboards/
│       └── datasources/
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md        # System architecture
│   ├── DEPLOYMENT.md          # Deployment guide
│   ├── API_KEYS.md            # Exchange API setup
│   ├── RESEARCH.md            # Research foundation
│   └── QUICK_START.md         # Quick start guide
│
└── data/                       # Data storage
    ├── logs/                  # Application logs
    └── historical/            # Historical data
```
