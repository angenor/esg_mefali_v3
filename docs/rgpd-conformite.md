# Conformité RGPD — ESG Mefali

> Document interne — Version 1.0 — Mise à jour : 2026-05-07

## 1. Cadre légal applicable

ESG Mefali traite des données personnelles dans un contexte panafricain. Les régimes
juridiques applicables sont :

- **RGPD européen** (Règlement UE 2016/679) : applicable aux PME utilisatrices basées
  dans l'Union européenne ou ayant des résidents de l'UE comme contacts
  professionnels.
- **Loi ivoirienne 2013-450** du 19 juin 2013 relative à la protection des
  données à caractère personnel (Côte d'Ivoire).
- **Règlement UEMOA n° 20/2010/CM/UEMOA** du 1er octobre 2010 portant
  Organisation et Fonctionnement de l'Autorité de Régulation des
  Télécommunications de la zone UEMOA, incluant les dispositions relatives à
  la protection des données.
- **Loi sénégalaise n° 2008-12** du 25 janvier 2008 relative à la protection
  des données à caractère personnel.

## 2. Checklist de conformité

| # | Item | Statut MVP | Notes |
|---|------|-----------|-------|
| 1 | Politique de confidentialité publiée | ✅ | `/legal/privacy` v1.0 |
| 2 | Registre des traitements | ⚠️ Partiel | Documenté ici, registre formel à finaliser post-MVP |
| 3 | DPO formalisé | ⏳ Post-MVP | Contact temporaire `privacy@esg-mefali.com` |
| 4 | Page « Mes Données » utilisateur | ✅ | `/mes-donnees` (inventaire + export + suppression) |
| 5 | Consentements granulaires | ✅ | 7 types granulaires, table `consents` |
| 6 | Helper applicatif `require_consent` | ✅ | `app/core/consent.py` + scanner CI |
| 7 | Droit d'accès (Art. 15) | ✅ | Export JSON exhaustif |
| 8 | Droit à l'effacement (Art. 17) | ✅ | Suppression compte J+30 + cron purge |
| 9 | Droit à la portabilité (Art. 20) | ✅ | Export JSON structuré |
| 10 | Durée de conservation documentée | ✅ | Audit log : 6 ans après anonymisation |
| 11 | Sous-traitants documentés | ✅ | Cf. `docs/hosting-and-data-residency.md` |
| 12 | Chiffrement at-rest | ✅ | AES-256 (provider) |
| 13 | Anonymisation lors de la purge | ✅ | UPDATE en place audit_log |
| 14 | Audit log append-only | ✅ | F03 — triggers PostgreSQL |
| 15 | Multi-tenant strict | ✅ | F02 — RLS PostgreSQL |
| 16 | Acceptation politique à l'inscription | ✅ | Checkbox obligatoire `/register` |
| 17 | Lien `/legal/privacy` dans tous les footers | ✅ | Layouts public + default |
| 18 | Cookies analytics tiers | ✅ | Aucun (pas de banner cookies requis) |
| 19 | Notification de violation 72h | ⏳ Post-MVP | Procédure documentée à venir |
| 20 | Privacy by Design / Default | ✅ | Consents par défaut au minimum nécessaire |

## 3. Processus d'exercice des droits utilisateurs

### 3.1 Droit d'accès (Art. 15 RGPD)

L'utilisateur peut consulter à tout moment :
- **L'inventaire** de ses données via `/mes-donnees → Inventaire`.
- **L'export complet JSON** via `/mes-donnees → Exporter mes données`.

L'export contient un fichier ZIP avec :
- `data.json` exhaustif (toutes les tables `account_id`).
- `documents/manifest.json` avec URLs signées 24h pour les fichiers physiques.
- `README.md` explicatif.

Délai max : 30 secondes (mode synchrone, ≤ 100 MB) ou notification email
(mode asynchrone, 7 jours de validité).

### 3.2 Droit à la rectification (Art. 16 RGPD)

L'utilisateur peut modifier son profil entreprise via `/profile`, ses
projets via `/projects/{id}/edit`, ses consentements via
`/mes-donnees → Consentements`. Les modifications sont tracées dans
`audit_log`.

### 3.3 Droit à l'effacement (Art. 17 RGPD)

Suppression du compte avec délai de grâce 30 jours :

1. Utilisateur va sur `/mes-donnees → Supprimer`.
2. Clic « Supprimer mon compte définitivement ».
3. Triple confirmation (consequences + password + texte « SUPPRIMER »).
4. `accounts.deletion_scheduled_at = now() + 30 days`.
5. Email de confirmation avec lien d'annulation.
6. À J+30 : cron `scripts/purge_scheduled_deletions.py` purge les données.
7. Audit_log anonymisé (`user_id=NULL, account_id=NULL`, payload filtré PII).

### 3.4 Droit à la portabilité (Art. 20 RGPD)

L'export JSON structuré permet de transférer ses données vers un autre
service. Le schéma est documenté dans le `README.md` du ZIP et dans
`specs/027-rgpd-mes-donnees-consents/contracts/me-data.md`.

### 3.5 Droit d'opposition (Art. 21 RGPD)

L'utilisateur peut révoquer un consentement à tout moment via
`/mes-donnees → Consentements`. La révocation prend effet immédiatement
(les futures requêtes vers les services concernés retournent 403).

## 4. Coordonnées de contact

| Rôle | Contact |
|------|---------|
| DPO (post-MVP) | À nommer avant déploiement production |
| Privacy Officer (MVP) | `privacy@esg-mefali.com` |
| Délais de réponse RGPD | 30 jours max (Art. 12.3) |
| Réclamation autorité de contrôle | CNIL (FR), CDP (SN), CDPDP (CI) |

## 5. Gabarits de réponse aux demandes RGPD

### 5.1 Accusé de réception (J+1)

> Bonjour,
>
> Nous avons bien reçu votre demande d'exercice de droit RGPD du [date].
> Conformément à l'article 12.3 du RGPD, nous vous répondrons sous 30 jours
> calendaires (avant le [date+30]).
>
> Référence dossier : RGPD-{account_id}-{date}
>
> Cordialement,
> L'équipe ESG Mefali — privacy@esg-mefali.com

### 5.2 Réponse droit d'accès

> Bonjour,
>
> Faisant suite à votre demande d'accès à vos données, vous trouverez
> ci-joint l'export complet en format JSON. Vous pouvez également générer
> ce même export à tout moment via votre espace `/mes-donnees`.
>
> Cordialement,
> L'équipe ESG Mefali — privacy@esg-mefali.com

### 5.3 Réponse droit à l'effacement

> Bonjour,
>
> Votre demande de suppression a été enregistrée. Conformément à notre
> politique, votre compte sera effectivement supprimé le [date+30 jours].
> Pendant ce délai, vous pouvez annuler la suppression en cliquant sur le
> lien dans l'email précédent ou via votre espace `/mes-donnees`.
>
> Cordialement,
> L'équipe ESG Mefali — privacy@esg-mefali.com

## 6. Historique des versions

| Version | Date | Auteur | Changements |
|---------|------|--------|-------------|
| 1.0 | 2026-05-07 | Équipe ESG Mefali | Version initiale (F05 MVP) |
