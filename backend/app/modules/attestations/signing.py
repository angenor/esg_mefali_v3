"""Couche cryptographique Ed25519 pour les attestations (F08 — T018).

Singleton ``SigningKeyStore`` chargeant la clé privée depuis
``settings.attestation_private_key_pem`` (env var ``ATTESTATION_PRIVATE_KEY_PEM``).

API publique :

- :func:`build_canonical_payload` — sérialise un payload en JSON canonique
  (sort_keys=True, separators=(',', ':')) pour signature reproductible.
- :func:`sign_payload` — retourne base64 de la signature Ed25519.
- :func:`verify_signature` — valide une signature base64 contre un payload canonique.
- :func:`get_public_key_pem` — expose la clé publique PEM pour vérification offline.

La clé privée n'est JAMAIS exposée hors du processus. Le cache en mémoire
(``SigningKeyStore``) est un objet thread-safe via les garanties Python sur
les imports modules. Pour les tests, un helper ``_reset_for_testing()`` est
exposé permettant de réinitialiser le singleton entre fixtures.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
from datetime import datetime
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class SigningKeyError(RuntimeError):
    """Erreur lors du chargement ou de l'usage de la clé Ed25519."""


class SigningKeyStore:
    """Singleton chargeant la clé privée Ed25519 et exposant sign/verify.

    Lazy-loading : la clé n'est chargée qu'au premier appel à
    :meth:`get_instance`. En production, ``settings.attestation_private_key_pem``
    DOIT être renseignée. En développement/tests, si vide, une paire éphémère
    est générée (warning logué).
    """

    _instance: "SigningKeyStore | None" = None
    _lock = threading.Lock()

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        public_key: Ed25519PublicKey,
        public_key_id: str,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._public_key_id = public_key_id

    @classmethod
    def get_instance(cls) -> "SigningKeyStore":
        """Retourne l'instance singleton (la crée si nécessaire)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._build_from_settings()
        return cls._instance

    @classmethod
    def _build_from_settings(cls) -> "SigningKeyStore":
        """Construit le store depuis les settings (env var)."""
        pem_string = settings.attestation_private_key_pem.strip()
        public_key_id = settings.attestation_public_key_id or "v1"

        if not pem_string:
            # Pas de clé en production = bloquant.
            if settings.env == "production":
                raise SigningKeyError(
                    "ATTESTATION_PRIVATE_KEY_PEM est requise en production. "
                    "Exécutez `python scripts/generate_attestation_keypair.py` "
                    "pour bootstrapper une paire de clés."
                )
            # Dev/tests : génération éphémère.
            logger.warning(
                "ATTESTATION_PRIVATE_KEY_PEM non défini — génération d'une paire "
                "éphémère (mode dev/tests). NE PAS utiliser en production."
            )
            private_key = Ed25519PrivateKey.generate()
            return cls(
                private_key=private_key,
                public_key=private_key.public_key(),
                public_key_id=public_key_id,
            )

        # Décoder les \n littéraux qui peuvent venir d'un .env mono-ligne.
        if "\\n" in pem_string and "-----BEGIN" in pem_string:
            pem_string = pem_string.replace("\\n", "\n")

        try:
            private_key_obj = serialization.load_pem_private_key(
                pem_string.encode("utf-8"),
                password=None,
            )
        except Exception as exc:  # ValueError, InvalidKey, UnsupportedAlgorithm…
            raise SigningKeyError(
                f"Impossible de charger ATTESTATION_PRIVATE_KEY_PEM : {exc}"
            ) from exc

        if not isinstance(private_key_obj, Ed25519PrivateKey):
            raise SigningKeyError(
                "ATTESTATION_PRIVATE_KEY_PEM n'est pas une clé Ed25519 (type "
                f"{type(private_key_obj).__name__})."
            )

        return cls(
            private_key=private_key_obj,
            public_key=private_key_obj.public_key(),
            public_key_id=public_key_id,
        )

    @classmethod
    def initialize(cls) -> "SigningKeyStore":
        """Force le chargement au démarrage (utilisé par le lifespan FastAPI).

        Exigible en production : si la clé est absente ou invalide, l'erreur
        est levée immédiatement (fail-fast au boot).
        """
        return cls.get_instance()

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Réinitialise le singleton (test fixtures uniquement)."""
        with cls._lock:
            cls._instance = None

    @property
    def public_key_id(self) -> str:
        return self._public_key_id

    def sign(self, canonical: bytes) -> bytes:
        """Retourne la signature Ed25519 brute (64 bytes)."""
        return self._private_key.sign(canonical)

    def verify(self, signature: bytes, canonical: bytes) -> bool:
        """Vérifie la signature ; retourne True/False (catch ``InvalidSignature``)."""
        try:
            self._public_key.verify(signature, canonical)
            return True
        except InvalidSignature:
            return False

    def get_public_key_pem(self) -> str:
        """Retourne la clé publique PEM (Subject Public Key Info)."""
        pem_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem_bytes.decode("ascii")


# ----------------------------------------------------------------------
# Fonctions de haut niveau
# ----------------------------------------------------------------------


def _json_default(obj: Any) -> Any:
    """Sérialiseur JSON pour types non standards (UUID, datetime…)."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        # ISO 8601 avec timezone ; pas de microsecondes pour stabilité.
        return obj.isoformat()
    raise TypeError(f"Type non sérialisable JSON : {type(obj).__name__}")


def _normalize_datetime(dt: datetime | str) -> str:
    """Normalise un datetime pour signature canonique : ISO 8601 UTC sans microsecondes.

    Garantit la reproductibilité même quand la BDD retourne un datetime
    naïf (cas SQLite). Si le datetime est naïf, on assume UTC. Microsecondes
    toujours strippées pour éviter les variations de précision DB.
    """
    if isinstance(dt, str):
        return dt
    from datetime import timezone as _tz

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz.utc)
    else:
        dt = dt.astimezone(_tz.utc)
    dt = dt.replace(microsecond=0)
    return dt.isoformat()


def build_canonical_payload(
    *,
    attestation_id: UUID | str,
    scores: dict[str, int],
    referential_snapshot: list[dict[str, Any]],
    pdf_hash_sha256: str,
    valid_from: datetime,
    valid_until: datetime,
) -> str:
    """Sérialise le payload en JSON canonique pour signature.

    Garanties :

    - clés alphabétiquement ordonnées (``sort_keys=True``)
    - pas d'espaces dans les séparateurs (``separators=(',', ':')``)
    - encodage UTF-8 strict (pas de BOM)
    - datetimes normalisés UTC ISO 8601 sans microsecondes
    - reproductible côté Python, Node.js, Go avec une lib JSON canonique
    """
    payload = {
        "attestation_id": str(attestation_id),
        "scores": scores,
        "referential_snapshot": referential_snapshot,
        "pdf_hash_sha256": pdf_hash_sha256,
        "valid_from": _normalize_datetime(valid_from),
        "valid_until": _normalize_datetime(valid_until),
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def sign_payload(canonical: str) -> str:
    """Signe un payload canonique (str UTF-8) → signature base64 ASCII."""
    store = SigningKeyStore.get_instance()
    signature = store.sign(canonical.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def verify_signature(signature_b64: str, canonical: str) -> bool:
    """Vérifie une signature base64 contre un payload canonique."""
    store = SigningKeyStore.get_instance()
    try:
        signature_bytes = base64.b64decode(signature_b64.encode("ascii"), validate=True)
    except Exception:  # noqa: BLE001 — un base64 invalide → signature invalide.
        return False
    if len(signature_bytes) != 64:
        # Signature Ed25519 = exactement 64 bytes ; toute autre taille = invalide.
        return False
    return store.verify(signature_bytes, canonical.encode("utf-8"))


def get_public_key_pem() -> str:
    """Expose la clé publique PEM (utilisé par l'endpoint public)."""
    return SigningKeyStore.get_instance().get_public_key_pem()


def get_public_key_id() -> str:
    """Expose l'identifiant de la clé publique active."""
    return SigningKeyStore.get_instance().public_key_id
