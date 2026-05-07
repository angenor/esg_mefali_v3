"""F04 — Exceptions du module currency."""

from __future__ import annotations


class NoRateAvailableError(Exception):
    """Aucun taux n'est disponible pour la paire (base, quote) demandée."""

    def __init__(self, base: str, quote: str, *args: object) -> None:
        super().__init__(
            f"no exchange rate available for pair {base}/{quote}", *args,
        )
        self.base = base
        self.quote = quote


class ConversionPathUnavailableError(Exception):
    """Aucun chemin de conversion (direct ou pivot USD) n'est disponible."""

    def __init__(self, base: str, quote: str, *args: object) -> None:
        super().__init__(
            f"conversion path {base}/{quote} unavailable via USD pivot", *args,
        )
        self.base = base
        self.quote = quote


class FetchFailedError(Exception):
    """Le fetch HTTP exchangerate-api.com a échoué (timeout, 4xx, 5xx)."""

    NORMALIZED_MSG = "EXCHANGERATE_FETCH_FAILED"

    def __init__(self, reason: str, *args: object) -> None:
        super().__init__(f"{self.NORMALIZED_MSG}: {reason}", *args)
        self.reason = reason
