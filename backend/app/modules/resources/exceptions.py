"""F20 — Exceptions typées du module Resources."""

from __future__ import annotations

import uuid


class ResourceNotFoundError(Exception):
    """La ressource demandée n'existe pas."""

    def __init__(self, resource_id: uuid.UUID | str) -> None:
        self.resource_id = resource_id
        super().__init__(f"Resource {resource_id} not found")


class ResourceSlugConflictError(Exception):
    """Le slug est déjà utilisé par une autre ressource."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Slug '{slug}' already exists")


class ResourceSourceNotVerifiedError(Exception):
    """La source liée n'est pas en statut ``verified``."""

    def __init__(self, source_id: uuid.UUID | str, current_status: str) -> None:
        self.source_id = source_id
        self.current_status = current_status
        super().__init__(
            f"Source {source_id} has status '{current_status}', must be 'verified'"
        )


class ResourceFourEyesViolationError(Exception):
    """Violation du workflow 4-yeux (publisher == creator)."""

    def __init__(self) -> None:
        super().__init__("verified_by must differ from created_by (4-yeux)")


class ResourceInvalidStatusError(Exception):
    """Transition de statut invalide."""

    def __init__(self, current: str, action: str) -> None:
        self.current = current
        self.action = action
        super().__init__(
            f"Cannot perform '{action}' on resource in status '{current}'"
        )


class ResourceTypeFieldMismatchError(Exception):
    """Cohérence type ↔ champs (ex: video sans video_url)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ResourceVideoUrlInvalidError(Exception):
    """video_url hors whitelist (YouTube/Vimeo/local)."""

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"Video URL '{url}' is not in the allowed providers")


class IntermediaryNotFoundError(Exception):
    """L'intermédiaire référencé n'existe pas."""

    def __init__(self, intermediary_id: uuid.UUID | str) -> None:
        self.intermediary_id = intermediary_id
        super().__init__(f"Intermediary {intermediary_id} not found")
