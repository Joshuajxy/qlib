# Cryptocurrency Support Implementation Summary

## Overview
This document summarizes the implementation of cryptocurrency data support in Qlib, designed to work alongside existing stock market data with the same interface and functionality.

## Changes Made

### 1. Added Crypto Constant
**File:** `qlib/constant.py`
- Added `REG_CRYPTO = "crypto"` constant for cryptocurrency region identification

### 2. Updated Configuration System
**File:** `qlib/config.py`
- Imported `REG_CRYPTO` constant
- Added cryptocurrency-specific region configuration to `_default_region_config`
- Added crypto-specific parameters (trade_unit=1, limit_threshold=None, deal_price="close")

### 3. Enhanced Data Collection
**File:** `scripts/data_collector/crypto/collector.py`
- Updated data collection to map crypto data to stock-like fields (open, high, low, close, volume)
- Improved normalization function to handle crypto data properly
- Added numpy import for data processing

### 4. Created Crypto Data Provider Module
**File:** `qlib/data/crypto_provider.py`
- Created comprehensive cryptocurrency data provider classes:
  - `CryptoCalendarProvider`: Handles 24/7 crypto calendar
  - `CryptoInstrumentProvider`: Manages crypto instruments
  - `CryptoFeatureProvider`: Handles crypto-specific features
  - `CryptoExpressionProvider`: Processes crypto expressions with field mapping
  - `CryptoDatasetProvider`: Manages crypto datasets
- Added initialization function `init_crypto_data()` for easy setup
- Included proper field name mapping for compatibility with existing alpha factors

### 5. Updated Data Registration System
**File:** `qlib/data/data.py`
- Enhanced `register_all_wrappers()` to support crypto-specific provider registration
- Added conditional logic to use crypto providers when `data_type == 'crypto'`

## Key Features

### 1. Same Interface as Stock Data
- Uses identical API: `D.instruments()`, `D.features()`, etc.
- Supports same field names: `$close`, `$open`, `$high`, `$low`, `$volume`
- Compatible with existing alpha factors without modification

### 2. Crypto-Specific Enhancements
- 24/7 market calendar support
- Crypto-specific region configuration
- Appropriate trade unit (1) and no limit thresholds

### 3. Data Processing Compatibility
- Crypto data is structured to match stock data format
- Field name mapping ensures compatibility with existing expressions
- Same data pipeline (collection, normalization, dumping) as stocks

## Usage Example

```python
import qlib
from qlib.data.crypto_provider import init_crypto_data
from qlib.data import D

# Initialize with cryptocurrency data
init_crypto_data(provider_uri="~/.qlib/qlib_data/crypto_data")

# Use the same interface as stock data
df = D.features(D.instruments(market="crypto"), ["$close", "$volume"], freq="day")

# Existing alpha factors work without modification
dataset = D.features(D.instruments("crypto"), 
                     ["$close/$open-1", "Ref($close, -1)/$close-1"], 
                     start_time="2020-01-01", 
                     end_time="2022-01-01", 
                     freq="day")
```

## Data Collection Process

1. **Collect Data:**
   ```bash
   cd scripts/data_collector/crypto
   python collector.py download_data --source_dir ~/.qlib/crypto_data/source/1d --start 2015-01-01 --end 2022-12-31 --delay 1 --interval 1d
   ```

2. **Normalize Data:**
   ```bash
   python collector.py normalize_data --source_dir ~/.qlib/crypto_data/source/1d --normalize_dir ~/.qlib/crypto_data/normalize/1d --interval 1d --date_field_name date
   ```

3. **Dump to Qlib Format:**
   ```bash
   cd ../../..  # back to main directory
   python dump_bin.py dump_all --data_path ~/.qlib/crypto_data/normalize/1d --qlib_dir ~/.qlib/qlib_data/crypto_data --freq day --date_field_name date --include_fields open,high,low,close,volume
   ```

## Benefits

1. **Seamless Integration:** Crypto data works with the same code as stock data
2. **Reusability:** Existing alpha factors and strategies work without modification
3. **Consistency:** Same data processing pipeline and quality standards as stock data
4. **Flexibility:** Can be used independently or combined with stock data
5. **Maintainability:** Follows existing Qlib patterns and conventions

## Testing

The implementation has been tested for:
- Constant definitions and imports
- Configuration system integration
- Module imports and structure
- Compatibility with existing interfaces

## Directory Structure

```
qlib/
├── constant.py                    # Added REG_CRYPTO constant
├── config.py                      # Added crypto config support
├── data/
│   ├── crypto_provider.py         # New crypto provider module
│   └── data.py                    # Enhanced registration system
└── scripts/data_collector/crypto/
    └── collector.py               # Enhanced data collection
```