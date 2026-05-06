"""Seed CLI : créer un utilisateur ADMIN (role='ADMIN', account_id=NULL).

Usage::

    cd backend && source venv/bin/activate
    python -m app.scripts.seed_admin --email admin@esg.com \
        --password 'secret-strong' --full-name "Admin Principal"

Le script s'exécute hors du serveur (pas d'endpoint public). Il connecte la
base via ``settings.database_url`` (asyncpg).

F02 — un Admin n'est rattaché à AUCUN Account ; la contrainte CHECK
``users_role_account_consistency`` impose ``account_id IS NULL`` quand
``role = 'ADMIN'``.

Sortie : retourne le UUID du user créé sur stdout (un par ligne) pour
faciliter l'intégration dans des scripts plus larges.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.user import User


async def _create_admin(
    *, email: str, password: str, full_name: str
) -> str:
    """Crée un utilisateur ADMIN et retourne son ID."""
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Vérification d'unicité
        existing = await session.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(
                f"Un utilisateur avec l'email '{email}' existe déjà."
            )
        admin = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            company_name="ESG Mefali",  # placeholder, non significatif pour Admin
            role=UserRole.ADMIN.value,
            account_id=None,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return str(admin.id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed CLI pour créer un utilisateur ADMIN ESG Mefali."
    )
    parser.add_argument("--email", required=True, help="Adresse email de l'admin")
    parser.add_argument(
        "--password",
        required=True,
        help="Mot de passe (sera hashé via bcrypt)",
    )
    parser.add_argument(
        "--full-name",
        required=True,
        help="Nom complet de l'admin (ex: 'Admin Principal')",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        admin_id = asyncio.run(
            _create_admin(
                email=args.email,
                password=args.password,
                full_name=args.full_name,
            )
        )
    except ValueError as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERREUR INATTENDUE: {exc}", file=sys.stderr)
        return 2
    print(admin_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
