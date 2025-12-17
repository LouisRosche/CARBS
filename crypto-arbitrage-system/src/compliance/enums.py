"""
Compliance module enums

Tax and regulatory classification enums.
"""

from enum import Enum


class CostBasisMethod(Enum):
    """Tax lot identification methods"""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    HIFO = "hifo"  # Highest In, First Out (minimizes gains)
    SPECIFIC = "specific"  # Specific lot identification


class AssetClass(Enum):
    """Asset classification for regulatory reporting"""
    CRYPTOCURRENCY = "cryptocurrency"
    STABLECOIN = "stablecoin"
    DEFI_TOKEN = "defi_token"
    NFT = "nft"
    FIAT = "fiat"


class TaxJurisdiction(Enum):
    """Supported tax jurisdictions"""
    US = "us"
    UK = "uk"
    EU = "eu"
    CANADA = "canada"
    AUSTRALIA = "australia"
    OTHER = "other"
