"""Shared retry infrastructure for Claude API calls, used by app.graph,
app.pdf_extract, and app.protocol_extract so all three get the same
behavior rather than each reimplementing (or, worse, skipping) it.

client() disables the SDK's own hidden retry/backoff layer, which on a
429 waits however long the server's Retry-After header says -- observed
once taking 26 minutes on a single call, completely silently, while it
was stacked underneath call_with_retries below. Our one explicit, logged,
bounded retry is meant to be the only retry layer in play.
"""

from __future__ import annotations

import json
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    json.JSONDecodeError,  # includes a truncated/malformed structured-output response
    StopIteration,  # a structured-output response missing the expected text block
)


def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=0)


def call_with_retries(fn, *args, max_attempts: int = 3, base_delay: float = 1.0, **kwargs):
    fn_name = getattr(fn, "__name__", repr(fn))
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except RETRYABLE_ERRORS as exc:
            if attempt == max_attempts - 1:
                logger.warning("%s failed after %d attempts, giving up: %s", fn_name, max_attempts, exc)
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "%s failed (attempt %d/%d): %s -- retrying in %.1fs",
                fn_name,
                attempt + 1,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)
