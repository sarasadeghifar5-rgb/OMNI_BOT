"""
===========================================================
🚀 Enterprise High-Performance HTTP Client Pool (Singleton)
===========================================================
Provides a globally shared, high-throughput, persistent HTTP/2
connection pool for all AI model providers (CodeCraft, Atria,
Agnes, Gemini, OpenAI-compatible, etc.).

Features:
- Multiplexed HTTP/2 support (multiple streams per TCP connection)
- Keep-Alive connection reuse (eliminates TLS/TCP handshake latency)
- High concurrency limits (up to 500 connections)
- Fine-grained DNS and connection timeouts
"""

import httpx
import logging
from typing import Optional

logger = logging.getLogger("HttpClientPool")

_client: Optional[httpx.AsyncClient] = None

def get_shared_http_client() -> httpx.AsyncClient:
    """
    Returns the global persistent AsyncClient instance.
    Initializes lazily on first access.
    """
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(
            max_connections=500,
            max_keepalive_connections=150,
            keepalive_expiry=120.0
        )
        timeout = httpx.Timeout(
            timeout=180.0,
            connect=8.0,
            read=90.0,
            write=30.0,
            pool=10.0
        )
        _client = httpx.AsyncClient(
            http2=True,
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
        )
        logger.info("⚡ Enterprise HTTP/2 Shared Client Pool initialized.")
    return _client

async def close_shared_http_client():
    """Gracefully closes the global HTTP client on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("HTTP/2 Shared Client Pool closed.")
