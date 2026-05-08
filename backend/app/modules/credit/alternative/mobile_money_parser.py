"""F18 — Parsers CSV/Excel pour 4 fournisseurs Mobile Money.

Détecte automatiquement le format/encodage et normalise chaque ligne
en un dataclass immuable :class:`MobileMoneyTransactionRow`. Hash SHA-256
le contre-parti avant persistance (FR-003).

Caps MVP :
- Taille fichier ≤ 5 Mo.
- Lignes ≤ 50 000.
- 4 fournisseurs supportés : ``wave``, ``orange_money``, ``mtn_momo``, ``moov_money``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterator

logger = logging.getLogger(__name__)

# Caps MVP (FR-001, edge cases spec)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000

VALID_PROVIDERS: tuple[str, ...] = (
    "wave",
    "orange_money",
    "mtn_momo",
    "moov_money",
)


class ParserError(Exception):
    """Erreur de parsing récupérable (format / taille / encodage)."""


@dataclass(frozen=True)
class MobileMoneyTransactionRow:
    """Transaction MM normalisée prête pour persistance."""

    provider: str
    transaction_date: datetime
    direction: str  # 'incoming' | 'outgoing'
    amount: Decimal
    currency: str  # 'XOF' par défaut
    counterparty_hash: str  # SHA-256 hex
    balance_amount: Decimal | None = None
    balance_currency: str | None = None


@dataclass(frozen=True)
class ParseResult:
    """Résultat du parsing : lignes valides + erreurs ligne par ligne."""

    rows: list[MobileMoneyTransactionRow]
    rejected_count: int
    errors_summary: dict


def _hash_counterparty(value: str) -> str:
    """SHA-256 hex du contre-parti (jamais en clair)."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _detect_encoding(raw: bytes) -> str:
    """Détection encodage best-effort (fallback UTF-8)."""
    try:
        import chardet  # type: ignore
    except ImportError:
        chardet = None  # type: ignore

    if chardet is not None:
        result = chardet.detect(raw[:8192])
        encoding = result.get("encoding") or "utf-8"
        return encoding
    return "utf-8"


def _parse_amount(value: str) -> Decimal:
    """Convertit une chaîne montant (tolère espaces, virgule, point)."""
    cleaned = (value or "").replace(" ", "").replace(",", ".").strip()
    if not cleaned:
        raise ParserError("amount vide")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ParserError(f"amount invalide: {value!r}") from exc
    if amount < 0:
        raise ParserError("amount négatif")
    return amount.quantize(Decimal("0.01"))


def _parse_date(value: str) -> datetime:
    """Parse une date ISO/locale courante. Naive → UTC."""
    if not value:
        raise ParserError("date vide")
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]
    for fmt in candidates:
        try:
            dt = datetime.strptime(value.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ParserError(f"format date inconnu: {value!r}")


# Mapping colonnes par fournisseur (best-effort sur exports CSV publics).
# Convention : aliases multiples pour tolérer variantes locales.
_PROVIDER_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "wave": {
        "date": ("Date", "date", "Datetime"),
        "type": ("Type", "type", "direction"),
        "amount": ("Amount", "amount", "Montant"),
        "counterparty": ("Counterparty", "counterparty", "Contact", "Beneficiary"),
        "balance": ("Balance", "balance", "Solde"),
    },
    "orange_money": {
        "date": ("Date", "date"),
        "type": ("Operation", "operation", "Type"),
        "amount": ("Montant", "Amount", "amount"),
        "counterparty": ("Numero", "Numéro", "Counterparty", "counterparty"),
        "balance": ("Solde", "Balance"),
    },
    "mtn_momo": {
        "date": ("Date", "date", "Transaction Date"),
        "type": ("Type", "type"),
        "amount": ("Amount", "amount"),
        "counterparty": ("Counterparty", "counterparty", "Receiver"),
        "balance": ("Balance", "balance"),
    },
    "moov_money": {
        "date": ("Date", "date"),
        "type": ("Sens", "Type", "type"),
        "amount": ("Montant", "Amount"),
        "counterparty": ("Numero", "Counterparty", "counterparty"),
        "balance": ("Solde", "Balance"),
    },
}


def _resolve_column(row: dict, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in row and row[alias] is not None:
            return str(row[alias]).strip()
    # Tolérance casse / espaces
    lower_map = {k.lower().strip(): k for k in row.keys() if k}
    for alias in aliases:
        key = lower_map.get(alias.lower().strip())
        if key is not None and row[key] is not None:
            return str(row[key]).strip()
    return None


def _normalize_direction(raw: str | None) -> str:
    """Normalise type → incoming/outgoing."""
    if not raw:
        raise ParserError("direction manquante")
    val = raw.strip().lower()
    if val in {"in", "incoming", "credit", "received", "reception", "réception", "depot", "dépôt"}:
        return "incoming"
    if val in {"out", "outgoing", "debit", "sent", "envoi", "retrait", "paiement", "payment"}:
        return "outgoing"
    raise ParserError(f"direction inconnue: {raw!r}")


def parse_file(
    file_bytes: bytes,
    provider: str,
    default_currency: str = "XOF",
) -> ParseResult:
    """Parse un fichier CSV MM, retourne lignes valides + erreurs comptées.

    Lève ``ParserError`` si fichier trop gros / fournisseur inconnu / encodage
    impossible à détecter.
    """
    if provider not in VALID_PROVIDERS:
        raise ParserError(f"provider inconnu: {provider!r}")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ParserError(
            f"fichier trop volumineux ({len(file_bytes)} bytes, "
            f"max {MAX_FILE_SIZE_BYTES})"
        )

    encoding = _detect_encoding(file_bytes)
    try:
        text = file_bytes.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError):
        text = file_bytes.decode("utf-8", errors="replace")

    # Détection séparateur (csv.Sniffer fallback `,`)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    columns = _PROVIDER_COLUMNS[provider]

    rows: list[MobileMoneyTransactionRow] = []
    rejected = 0
    error_samples: list[dict] = []

    for idx, raw_row in enumerate(reader, start=2):  # ligne 1 = header
        if idx > MAX_ROWS + 1:
            raise ParserError(f"trop de lignes (>{MAX_ROWS})")
        try:
            date_str = _resolve_column(raw_row, columns["date"])
            type_str = _resolve_column(raw_row, columns["type"])
            amount_str = _resolve_column(raw_row, columns["amount"])
            counterparty = _resolve_column(raw_row, columns["counterparty"])
            balance_str = _resolve_column(raw_row, columns["balance"])

            if not (date_str and type_str and amount_str and counterparty):
                raise ParserError("colonne(s) requise(s) manquante(s)")

            tx = MobileMoneyTransactionRow(
                provider=provider,
                transaction_date=_parse_date(date_str),
                direction=_normalize_direction(type_str),
                amount=_parse_amount(amount_str),
                currency=default_currency,
                counterparty_hash=_hash_counterparty(counterparty),
                balance_amount=(_parse_amount(balance_str) if balance_str else None),
                balance_currency=(default_currency if balance_str else None),
            )
            rows.append(tx)
        except ParserError as exc:
            rejected += 1
            if len(error_samples) < 10:
                error_samples.append({"line": idx, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001 — logge mais continue
            rejected += 1
            if len(error_samples) < 10:
                error_samples.append({"line": idx, "reason": f"unexpected: {exc!r}"})

    summary = {
        "provider": provider,
        "encoding": encoding,
        "rejected": rejected,
        "errors": error_samples,
    }
    logger.info(
        "mm_parse_completed",
        extra={
            "provider": provider,
            "imported_rows": len(rows),
            "rejected_rows": rejected,
        },
    )
    return ParseResult(rows=rows, rejected_count=rejected, errors_summary=summary)


__all__ = [
    "MobileMoneyTransactionRow",
    "ParserError",
    "ParseResult",
    "VALID_PROVIDERS",
    "MAX_FILE_SIZE_BYTES",
    "MAX_ROWS",
    "parse_file",
]
