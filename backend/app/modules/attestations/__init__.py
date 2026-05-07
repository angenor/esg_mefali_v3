"""Module Attestation Vérifiable Ed25519 (F08 — Module 5.3).

Expose :

- ``signing`` : couche cryptographique Ed25519 (singleton ``SigningKeyStore``).
- ``qr`` : génération de QR codes PNG via ``segno``.
- ``pdf`` : génération du PDF d'attestation enrichi (WeasyPrint + Jinja2).
- ``service`` : orchestration générer/révoquer/vérifier.
- ``router`` : endpoints REST authentifiés (PME).
- ``admin_router`` : endpoints admin (cross-tenant).
- ``schemas`` : DTO Pydantic v2 (incluant ``VerificationResult`` discriminated union).
"""
