"""Configuration management"""
from dataclasses import dataclass
from typing import Dict, List
import yaml
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TradingConfig:
    mode: str
    min_spread_percent: float
    max_spread_percent: float
    max_position_usd: float
    max_daily_loss_usd: float = 100.0
    max_daily_trades: int = 20
    order_timeout_seconds: int = 30
    max_slippage_bps: int = 50

@dataclass  
class Config:
    trading: TradingConfig
    exchanges: Dict
    symbols: List[str]
    monitoring: Dict
    performance: Dict
    risk_management: Dict
    logging: Dict
    database: Dict
    redis: Dict

def load_config(path: str = "config/config.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(
        trading=TradingConfig(**data['trading']),
        exchanges=data['exchanges'],
        symbols=data['symbols'],
        monitoring=data['monitoring'],
        performance=data['performance'],
        risk_management=data['risk_management'],
        logging=data['logging'],
        database=data['database'],
        redis=data['redis']
    )
