"""Module mémoire contextuelle (F12).

Expose :
- ``embed_message``, ``search_history``, ``mask_secrets``, ``chunk_text``,
  ``purge_account_chunks`` : services bas niveau (cf. ``service.py``).
- ``MessageRecallResult`` : dataclass de retour pour ``search_history``.

Le hook SQLAlchemy ``after_insert`` sur ``Message`` est chargé via
``app.modules.memory.hooks`` (importer pour activer).
"""

from app.modules.memory.service import (
    MessageRecallResult,
    chunk_text,
    embed_message,
    mask_secrets,
    purge_account_chunks,
    search_history,
)

__all__ = [
    "MessageRecallResult",
    "chunk_text",
    "embed_message",
    "mask_secrets",
    "purge_account_chunks",
    "search_history",
]
