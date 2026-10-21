"""Shared desktop/server shutdown signal."""
from threading import Event

shutdown_requested = Event()
