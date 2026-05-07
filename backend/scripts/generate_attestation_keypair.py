"""Bootstrap one-shot : génère une paire Ed25519 pour les attestations F08.

Usage :

    python backend/scripts/generate_attestation_keypair.py [--id v1]

Imprime sur stdout :

    ATTESTATION_PRIVATE_KEY_PEM=<PEM mono-ligne avec \\n encodés>
    ATTESTATION_PUBLIC_KEY_PEM=<PEM mono-ligne avec \\n encodés>
    ATTESTATION_PUBLIC_KEY_ID=v1

Copier les 3 lignes dans le ``.env`` local (ou injecter en production via le
secret manager d'infra). NE JAMAIS commiter la clé privée dans git.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate_keypair(public_key_id: str) -> tuple[str, str, str]:
    """Génère une paire Ed25519 et la retourne au format PEM."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return private_pem, public_pem, public_key_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--id", default="v1",
        help="Identifiant de la clé publique (défaut : v1)",
    )
    parser.add_argument(
        "--format", choices=("env", "raw"), default="env",
        help="Format de sortie : env (mono-ligne avec \\n encodés) ou raw (multi-lignes)",
    )
    args = parser.parse_args()

    private_pem, public_pem, key_id = generate_keypair(args.id)
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    print(f"=== Generated Ed25519 Keypair (issued_at={now_iso}, public_key_id={key_id}) ===")
    print()
    if args.format == "env":
        # Format mono-ligne avec \n littéraux pour copy/paste dans .env
        priv_oneliner = private_pem.replace("\n", "\\n")
        pub_oneliner = public_pem.replace("\n", "\\n")
        print(f"ATTESTATION_PRIVATE_KEY_PEM={priv_oneliner}")
        print(f"ATTESTATION_PUBLIC_KEY_PEM={pub_oneliner}")
        print(f"ATTESTATION_PUBLIC_KEY_ID={key_id}")
    else:
        print("--- PRIVATE KEY (à conserver secrète) ---")
        print(private_pem)
        print("--- PUBLIC KEY (peut être publiée) ---")
        print(public_pem)
        print(f"--- public_key_id : {key_id} ---")

    print()
    print("# IMPORTANT :")
    print("# - Stockez ATTESTATION_PRIVATE_KEY_PEM dans votre secret manager (jamais en git).")
    print("# - ATTESTATION_PUBLIC_KEY_PEM peut être commitée si besoin (clé publique).")
    print("# - Pour rotation post-MVP : générer une paire v2 et conserver v1 pour vérifier")
    print("#   les attestations historiques.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
