"""Broker adapters. The SDK only needs a callback returning ``{symbol: signed_qty}``;
these are convenience wrappers for the two most common portable layers.
"""

from .base import BrokerAdapter

__all__ = ["BrokerAdapter"]
