"""Pipeline orchestration: document → extracted items → rules → formatted descriptions."""
from __future__ import annotations
import logging
from typing import Callable, Optional
from core.document_reader import read_document_smart, SmartParseError
from core.rules import apply_rules
from core.formatter import format_description

logger = logging.getLogger(__name__)


def process_document(
    source,
    source_type: str,
    openai_client,
    progress_cb: Optional[Callable] = None,
    on_chunk_items: Optional[Callable] = None,
) -> tuple[list[dict], int, str | None]:
    """
    Full pipeline: raw input → processed items with GGPL descriptions.

    Returns (items, skipped_count, error_message).
    error_message is None on success, a human-readable string on failure.
    """
    def _on_chunk(chunk_items):
        processed_chunk = []
        for item in chunk_items:
            item = apply_rules(item)
            item['ggpl_description'] = format_description(item)
            processed_chunk.append(item)
        if on_chunk_items:
            on_chunk_items(processed_chunk)

    try:
        raw_items, n_skipped = read_document_smart(
            source, source_type, openai_client,
            progress_cb=progress_cb,
            on_chunk_items=_on_chunk,
        )
    except SmartParseError as e:
        return [], 0, str(e)

    processed = []
    for item in raw_items:
        item = apply_rules(item)
        item['ggpl_description'] = format_description(item)
        processed.append(item)

    return processed, n_skipped, None
