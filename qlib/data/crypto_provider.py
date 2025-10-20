# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Cryptocurrency data provider module for Qlib.

This module extends Qlib's data providers to support cryptocurrency markets
with the same interface as traditional stock markets.
"""

from __future__ import division
from __future__ import print_function

import re
import abc
import copy
from typing import List, Union, Optional
from pathlib import Path

import numpy as np
import pandas as pd

from .data import (
    ProviderBackendMixin,
    CalendarProvider,
    InstrumentProvider,
    FeatureProvider,
    PITProvider,
    ExpressionProvider,
    DatasetProvider,
    LocalCalendarProvider,
    LocalInstrumentProvider,
    LocalFeatureProvider,
    LocalPITProvider,
    LocalExpressionProvider,
    LocalDatasetProvider,
    Cal,
    Inst,
    FeatureD,
    PITD,
    ExpressionD,
    DatasetD,
    D,
)
from .cache import DiskDatasetCache, H
from ..config import C
from ..utils import (
    Wrapper,
    init_instance_by_config,
    register_wrapper,
    get_module_by_module_path,
    parse_field,
    hash_args,
    normalize_cache_fields,
    code_to_fname,
    time_to_slc_point,
)
from ..utils.paral import ParallelExt
from .ops import Operators  # pylint: disable=W0611  # noqa: F401
from ..log import get_module_logger


class CryptoCalendarProvider(LocalCalendarProvider):
    """
    Cryptocurrency calendar provider.
    
    Since cryptocurrency markets operate 24/7, this provider handles 
    the unique calendar requirements of crypto markets.
    """
    def __init__(self, remote=False, backend={}, freq="day"):
        super().__init__(remote=remote, backend=backend)
        self.freq = freq

    def load_calendar(self, freq, future):
        """
        Load cryptocurrency calendar data.
        
        Parameters
        ----------
        freq : str
            frequency of read calendar file.
        future: bool
        
        Returns
        -------
        list
            list of timestamps
        """
        try:
            backend_obj = self.backend_obj(freq=freq, future=future).data
        except ValueError:
            if future:
                get_module_logger("data").warning(
                    f"load calendar error: freq={freq}, future={future}; return current calendar!"
                )
                backend_obj = self.backend_obj(freq=freq, future=False).data
            else:
                raise

        return [pd.Timestamp(x) for x in backend_obj]

    def calendar(self, start_time=None, end_time=None, freq="day", future=False):
        """
        Get cryptocurrency calendar in given time range.
        
        Parameters
        ----------
        start_time : str
            start of the time range.
        end_time : str
            end of the time range.
        freq : str
            time frequency, available: year/quarter/month/week/day.
        future : bool
            whether including future trading day.

        Returns
        ----------
        list
            calendar list
        """
        _calendar, _calendar_index = self._get_calendar(freq, future)
        if start_time == "None":
            start_time = None
        if end_time == "None":
            end_time = None
        # strip
        if start_time:
            start_time = pd.Timestamp(start_time)
            if start_time > _calendar[-1]:
                return np.array([])
        else:
            start_time = _calendar[0]
        if end_time:
            end_time = pd.Timestamp(end_time)
            if end_time < _calendar[0]:
                return np.array([])
        else:
            end_time = _calendar[-1]
        _, _, si, ei = self.locate_index(start_time, end_time, freq, future)
        return _calendar[si : ei + 1]


class CryptoInstrumentProvider(LocalInstrumentProvider):
    """
    Cryptocurrency instrument provider.
    
    Handles cryptocurrency-specific instrument management.
    """
    def __init__(self, backend={}):
        super().__init__(backend=backend)

    def _load_instruments(self, market, freq):
        # Add special handling for cryptocurrency market
        if market == "crypto" or market == C.REG_CRYPTO:
            # Load crypto-specific instruments
            return self._load_crypto_instruments(freq)
        return super()._load_instruments(market, freq)
    
    def _load_crypto_instruments(self, freq):
        """Load cryptocurrency instruments from backend."""
        # This will load crypto instruments specifically
        return self.backend_obj(market="crypto", freq=freq).data


class CryptoFeatureProvider(LocalFeatureProvider):
    """
    Cryptocurrency feature provider.
    
    Handles cryptocurrency-specific feature access.
    """
    def __init__(self, remote=False, backend={}):
        super().__init__(remote=remote, backend=backend)


class CryptoExpressionProvider(LocalExpressionProvider):
    """
    Cryptocurrency expression provider.
    
    Handles cryptocurrency-specific expression operations.
    """
    def __init__(self, time2idx=True):
        super().__init__(time2idx=time2idx)

    def expression(self, instrument, field, start_time=None, end_time=None, freq="day"):
        """
        Get cryptocurrency expression data.
        
        Supports special cryptocurrency field mappings:
        - $open, $high, $low, $close -> to cryptocurrency price data
        - $volume -> to cryptocurrency trading volume
        - $market_cap -> to market cap data
        """
        # Translate cryptocurrency field aliases if needed
        field = self._translate_crypto_field(field)
        return super().expression(instrument, field, start_time, end_time, freq)
    
    def _translate_crypto_field(self, field):
        """
        Translate cryptocurrency-specific field aliases to actual stored field names.
        """
        # This method can be expanded to support more cryptocurrency-specific aliases
        crypto_field_mapping = {
            "$open": "$open",
            "$high": "$high", 
            "$low": "$low",
            "$close": "$close",
            "$volume": "$volume",
            "$market_cap": "$market_cap",
            # Add more mappings as needed
        }
        
        if field in crypto_field_mapping:
            return crypto_field_mapping[field]
        return field


class CryptoDatasetProvider(LocalDatasetProvider):
    """
    Cryptocurrency dataset provider.
    
    Handles cryptocurrency-specific dataset operations.
    """
    def __init__(self, align_time: bool = True):
        super().__init__(align_time=align_time)


def register_crypto_wrappers(C):
    """
    Register cryptocurrency data providers with the configuration system.
    This function registers crypto-specific providers that work alongside
    the existing stock market providers.
    """
    logger = get_module_logger("data")
    module = get_module_by_module_path("qlib.data")

    # Register crypto calendar provider
    _calendar_provider = init_instance_by_config(C.crypto_calendar_provider, module)
    if getattr(C, "crypto_calendar_cache", None) is not None:
        _calendar_provider = init_instance_by_config(C.crypto_calendar_cache, module, provide=_calendar_provider)
    register_wrapper(Cal, _calendar_provider, "qlib.data")
    logger.debug(f"registering Cal {C.crypto_calendar_provider}-{C.crypto_calendar_cache}")

    # Register crypto instrument provider
    _instrument_provider = init_instance_by_config(C.crypto_instrument_provider, module)
    register_wrapper(Inst, _instrument_provider, "qlib.data")
    logger.debug(f"registering Inst {C.crypto_instrument_provider}")

    if getattr(C, "crypto_feature_provider", None) is not None:
        feature_provider = init_instance_by_config(C.crypto_feature_provider, module)
        register_wrapper(FeatureD, feature_provider, "qlib.data")
        logger.debug(f"registering FeatureD {C.crypto_feature_provider}")

    if getattr(C, "crypto_pit_provider", None) is not None:
        pit_provider = init_instance_by_config(C.crypto_pit_provider, module)
        register_wrapper(PITD, pit_provider, "qlib.data")
        logger.debug(f"registering PITD {C.crypto_pit_provider}")

    if getattr(C, "crypto_expression_provider", None) is not None:
        # Expression provider for cryptocurrency
        _eprovider = init_instance_by_config(C.crypto_expression_provider, module)
        if getattr(C, "expression_cache", None) is not None:
            _eprovider = init_instance_by_config(C.expression_cache, module, provider=_eprovider)
        register_wrapper(ExpressionD, _eprovider, "qlib.data")
        logger.debug(f"registering ExpressionD {C.crypto_expression_provider}-{C.expression_cache}")

    _dprovider = init_instance_by_config(C.crypto_dataset_provider, module)
    if getattr(C, "dataset_cache", None) is not None:
        _dprovider = init_instance_by_config(C.dataset_cache, module, provider=_dprovider)
    register_wrapper(DatasetD, _dprovider, "qlib.data")
    logger.debug(f"registering DatasetD {C.crypto_dataset_provider}-{C.dataset_cache}")

    register_wrapper(D, C.crypto_provider, "qlib.data")
    logger.debug(f"registering D {C.crypto_provider}")


def init_crypto_data(qlib_config=None, provider_uri: Union[str, Path, dict] = "~/.qlib/qlib_data/crypto_data", region=None, **kwargs):
    """
    Initialize Qlib with cryptocurrency data support.
    
    This function allows users to initialize Qlib with cryptocurrency data
    in the same way they would initialize it with stock data.
    
    Parameters
    ----------
    qlib_config : dict, optional
        Qlib configuration dictionary
    provider_uri : str or dict, optional
        Path to the cryptocurrency data directory
    region : str, optional
        Region identifier (should be 'crypto' for cryptocurrency data)
    **kwargs :
        Additional configuration parameters
        
    Example
    -------
    ```python
    import qlib
    from qlib.data.crypto_provider import init_crypto_data
    
    # Initialize with cryptocurrency data
    init_crypto_data(provider_uri="~/.qlib/qlib_data/crypto_data")
    
    # Use the same functions as with stock data
    from qlib.data import D
    df = D.features(D.instruments(market="crypto"), ["$close", "$volume"], freq="day")
    ```
    """
    import qlib
    from ..config import C
    
    # Prepare the config for cryptocurrency
    if region is None:
        region = C.REG_CRYPTO
    config = {
        "provider_uri": provider_uri,
        "region": region,
        **kwargs
    }
    
    # Initialize Qlib with the crypto configuration
    qlib.init(**config)
    
    return config


# Default crypto provider configurations
DEFAULT_CRYPTO_CONFIG = {
    "crypto_calendar_provider": "CryptoCalendarProvider",
    "crypto_instrument_provider": "CryptoInstrumentProvider", 
    "crypto_feature_provider": "CryptoFeatureProvider",
    "crypto_expression_provider": "CryptoExpressionProvider",
    "crypto_dataset_provider": "CryptoDatasetProvider",
    "crypto_provider": "LocalProvider",  # Using the same base provider as stocks but with crypto-specific components
}