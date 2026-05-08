# Bug 03 — Incohérence ORM/BDD sur `account_id` (nullable=True ORM, NOT NULL en BDD)

## Symptôme

Le modèle `Conversation` (et probablement d'autres modèles touchés par la migration F02) déclare `account_id` comme `nullable=True` au niveau ORM SQLAlchemy, mais la migration BDD a appliqué `NOT NULL` sur la colonne. Conséquences :

1. **Pas de validation côté ORM** : on peut instancier `Conversation(user_id=..., title=...)` sans `account_id`. L'erreur n'apparaît qu'au flush/commit, sous forme d'`IntegrityError` Postgres bruit (cf. bug initial qui causait le crash 500 du chatbot, déjà corrigé à coup de patch dans `chat.py` mais pas au niveau du modèle).
2. **Mypy / Pylance** ne peuvent pas signaler les usages incorrects à la compilation.
3. Les futurs développeurs créeront le même bug (oubli de `account_id`) sans avoir de garde-fou statique.

## Cause racine

CLAUDE.md indique pour F02 :
> Colonne `account_id UUID NOT NULL` ajoutée à 14 tables métier (migration 019).

Mais le modèle `backend/app/models/conversation.py:24-28` est resté :

```python
# F02 — multi-tenant
account_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("accounts.id", ondelete="RESTRICT"),
    nullable=True,
)
```

L'incohérence est un oubli de mise à jour de l'ORM lors de la migration F02. À auditer aussi sur les **13 autres tables métier** touchées (`messages`, `company_profiles`, `documents`, `esg_assessments`, `carbon_assessments`, `credit_scores`, `action_plans`, `action_items`, `fund_applications`, `interactive_questions`, etc.).

## Fichiers concernés

À **auditer** : tous les modèles SQLAlchemy dans `backend/app/models/` et `backend/app/modules/*/models.py`.

À **corriger** : tous les modèles dont la BDD a `account_id NOT NULL` mais l'ORM a `nullable=True`.

Vérification BDD :

```sql
SELECT table_name, is_nullable
FROM information_schema.columns
WHERE column_name = 'account_id'
  AND table_schema = 'public'
ORDER BY table_name;
```

## Tâche

1. **Audit** :
   - Lister toutes les tables avec colonne `account_id` et leur `is_nullable` réel (cf. requête SQL ci-dessus).
   - Pour chaque table, ouvrir le modèle ORM correspondant et noter le type déclaré.
   - Produire un tableau récapitulatif (table | BDD nullable | ORM nullable | action).

2. **Corriger les modèles incohérents** :
   - Pour chaque modèle où BDD = NOT NULL et ORM = nullable=True :
     - Changer `Mapped[uuid.UUID | None]` → `Mapped[uuid.UUID]`
     - Changer `nullable=True` → `nullable=False`
   - Cas particulier : si un modèle a logiquement vocation à supporter des admins (sans account_id), garder `nullable=True` côté ORM ET ajouter une migration pour relâcher la BDD. Pour le MVP, **tous les modèles métier doivent avoir un account_id** — les admins n'ont pas vocation à créer de Conversation, Message, etc. (cf. check constraint `users_role_account_consistency`).

3. **Conséquence sur le code applicatif** :
   - Tout instanciation `Conversation(...)` ou `Message(...)` sans `account_id` deviendra une erreur Pylance/mypy. **C'est le comportement voulu**.
   - Vérifier que tous les sites de création passent désormais `account_id` (le bug initial du chatbot a déjà corrigé `chat.py` ; vérifier les autres modules).

4. **Tests** :
   - Pas de nouveau test fonctionnel requis (la contrainte BDD est déjà en place).
   - Vérifier que `pytest backend/tests/ -v` reste vert.
   - Lancer `mypy backend/app/` ou `pyright backend/app/` pour valider que le typage strict détecte les usages incorrects.

5. **Git** :
   - Diff minimal : uniquement les lignes `Mapped[...]` et `nullable=...` modifiées dans les modèles.
   - **Pas** de migration Alembic (la BDD est déjà NOT NULL).
   - Message commit : `fix(F02): aligner annotations ORM account_id avec contrainte NOT NULL BDD`.

## Critères d'acceptation

- [ ] Tableau d'audit produit en début de PR (description) listant les ≤14 tables et leur état avant/après.
- [ ] Tous les modèles concernés ont `Mapped[uuid.UUID]` (sans `| None`) et `nullable=False`.
- [ ] `pytest backend/tests/ -v` passe (round-trip vert).
- [ ] `pyright` ou `mypy` ne signale aucun nouveau warning sur les modèles modifiés.
- [ ] Aucun changement BDD (pas de migration Alembic).
- [ ] Aucune régression : créer une `Conversation` avec `account_id` continue de fonctionner ; en omettre déclenche désormais une erreur de type **avant** l'INSERT.

## Notes

- Bug **non bloquant** : le chatbot fonctionne déjà (les 3 instanciations dans `chat.py` ont été patchées). Ce ticket est une dette technique de cohérence ORM/BDD.
- Priorité : moyenne. À traiter après les bugs 01 et 02 qui touchent fonctionnellement la mémoire F12.
- Si on découvre qu'un modèle a légitimement besoin de `nullable=True` (ex: pour des entités globales pré-F02), ouvrir une discussion avant de modifier — ne pas forcer le NOT NULL à l'ORM si la BDD doit aussi être modifiée (qui nécessiterait une migration descendante).
- Vérifier en parallèle si les helpers/factories de tests créent des entités sans `account_id` — si oui, les corriger avec un `account_id` par défaut.
