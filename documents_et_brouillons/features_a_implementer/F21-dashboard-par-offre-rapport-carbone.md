# F21 — Dashboard par Offre + Carte Intermédiaires + Rapport Carbone PDF

**Module(s) source(s)** : Module 7.1 (Dashboard Principal), Module 7.2 (Rapports), Module 4 (Rapport Carbone PDF)
**Priorité** : P1 — complétion Modules 7 et 4
**Dépendances** : F01 (sources), F03 (audit log PME), F07 (Offer), F08 (attestation), F11 (Map block), F17 (carbone sourcé)
**Estimation** : 2 sprints

## Contexte & motivation

**Module 7.1 — Dashboard Principal**
- Statut candidatures **par OFFRE** (couple Fonds × Intermédiaire) — étape, prochain rappel, prochaine échéance
- **Carte des intermédiaires actifs** et de leurs accréditations en cours
- Scores cliquables vers sources (F01)

**Module 7.2 — Rapports**
- Rapport carbone téléchargeable en PDF (actuellement absent)
- Audit log (Module 0.4 / F03) visible par utilisateurs PME
- Page "Mes données" (couvert par F05)

**Module 4 — Rapport Carbone PDF**
- Visualisations sourcées (kpi card + charts)
- Annexe "Sources et références" auto-générée

**État actuel** :
- `_get_financing_summary` (`backend/app/modules/dashboard/service.py`) regroupe candidatures **par status global**, pas par Offre
- Pas de carte intermédiaires sur le dashboard
- Pas de scores cliquables vers sources (Module 0.1 absent)
- **Aucun endpoint `/api/reports/carbon/{id}/generate`** : recherche dans `app/modules/reports/router.py` confirme que seul ESG est géré
- Le module carbon n'expose aucun export PDF

**Conséquences** :
- Vue dashboard incomplète : impossible de voir "mes 3 candidatures GCF/BOAD à différentes étapes"
- Pas de visualisation géographique des intermédiaires
- Le rapport carbone PDF — promis dans Module 7.2 — n'existe pas

## User stories

- **PME** : « Sur le dashboard, je veux voir 3 cards "candidatures actives" : 1) GCF via BOAD - étape "Instruction", J-15 deadline ; 2) SUNREF Ecobank - étape "Préparation dossier", aucune deadline ; 3) FEM via PNUD - "Dossier déposé", attente. »
- **PME** : « Je veux voir une carte UEMOA avec les intermédiaires actifs (BOAD à Lomé, PNUD à Abidjan, Ecobank à Lomé), avec popup au clic. »
- **PME** : « Je veux pouvoir générer un rapport carbone PDF avec breakdown par catégorie, équivalences en FCFA, plan de réduction sourcé, annexe Sources. »
- **PME** : « Je veux pouvoir cliquer sur le score ESG affiché en card pour voir le détail multi-référentiels (F13) avec sources (F01). »

## Périmètre fonctionnel

### Dashboard granularité par Offre

Refactor `backend/app/modules/dashboard/service.py:_get_financing_summary` :
- Au lieu de retourner `application_statuses: dict[str, int]` global, retourner `applications_by_offer: list[ApplicationCard]` :
  ```json
  [
    {
      "application_id": "...",
      "offer_id": "...",
      "fund_name": "GCF",
      "intermediary_name": "BOAD",
      "fund_logo_url": "...",
      "intermediary_logo_url": "...",
      "status": "submitted_to_intermediary",
      "current_step": "Instruction par BOAD",
      "next_deadline": "2026-04-15",
      "next_reminder": "Relancer dans 3 jours",
      "last_activity_at": "2026-04-01"
    },
    ...
  ]
  ```
- Utilisé pour rendre 1 card par application sur le dashboard

Composant frontend : `<ApplicationStatusCard>` qui affiche les infos + bouton "Voir détail"

### Carte intermédiaires actifs

Section `pages/dashboard.vue` : `<IntermediariesMap>`
- Utilise `<MapBlock>` (F11) avec markers :
  - 1 par intermédiaire actif (lié à un projet ou candidature de l'utilisateur)
  - Type `intermediary` avec popup `{name, type, country, accreditations: [fund_names], applications_count: N}`
- Layer overlay UEMOA (8 pays)
- Lien vers fiche intermédiaire `/financing/intermediaries/{id}`

### Scores cliquables vers sources

- Composant `<ScoreCard>` (existant, `frontend/app/components/dashboard/ScoreCard.vue`) : ajouter `<SourceLink>` (F01) à côté du score
- Click → `<SourceModal>` avec détails

### Rapport carbone PDF (NOUVEAU)

Endpoint `POST /api/reports/carbon/{assessment_id}/generate` :
- Rend `Report` row (table existante) avec `report_type='carbon'`
- Génère PDF via WeasyPrint avec template `carbon_report.html`

Sections du PDF :
1. Cover : logo, titre, identité PME, période évaluation
2. Synthèse : empreinte totale tCO2e + KPI card (avec source ADEME)
3. Breakdown par catégorie : pie chart + table
4. Comparaison sectorielle : bar chart
5. Évolution multi-années (si plusieurs assessments)
6. Plan de réduction : actions priorisées avec sources
7. Équivalences pédagogiques (FCFA économisés, etc.)
8. Méthodologie : facteurs ADEME/IPCC utilisés
9. **Annexe "Sources et références"** auto-générée (F01)

Endpoint `GET /api/reports/{report_id}/download` réutilisé.

Frontend `pages/reports/index.vue` : ajouter onglet "Rapports Carbone" (en parallèle "Rapports ESG").

Bouton "Générer rapport carbone PDF" sur `pages/carbon/results.vue`.

### Audit log visible PME (lien F03)

Page `/historique` créée par F03. Référencée dans le dashboard via card "Activité récente" qui pointe vers `/historique` pour voir l'historique complet.

### Mise à jour dashboard endpoint

`GET /api/dashboard/summary` retourne :
```json
{
  "esg": {...},
  "carbon": {...},
  "credit": {...},
  "financing": {
    "applications_by_offer": [...],
    "active_intermediaries": [
      {"id": "...", "name": "BOAD", "country": "TG", "lat": 6.13, "lon": 1.21, ...},
      ...
    ],
    "next_deadlines": [...]
  },
  "next_actions": [...],
  "recent_activity": [...],
  "badges": [...]
}
```

## Hors-scope (post-MVP)

- Dashboard customizable (drag & drop widgets)
- Comparaison période (mois sur mois)
- Notifications push browser
- Cohort comparison (vous vs autres PME secteur)
- Export dashboard en PDF
- Partage public d'un dashboard anonymisé

## Exigences techniques

### Backend

- Refactor `backend/app/modules/dashboard/service.py` : `_get_financing_summary` granulaire par offre
- Endpoint `GET /api/dashboard/active-intermediaries` (avec coordonnées)
- Module `app/modules/reports/carbon/` :
  - `service.py` : `generate_carbon_report(assessment_id)`
  - Template `templates/carbon_report.html`
- Endpoint `POST /api/reports/carbon/{assessment_id}/generate`
- Tool LangChain `generate_carbon_report` (similaire au tool ESG existant)
- Tests :
  - Test dashboard : applications_by_offer reflète les 3 candidatures actives
  - Test carbon report : PDF généré avec breakdown + annexe sources
  - Test multi-tenant : un user voit ses applications, pas celles d'autres accounts

### Frontend

- Composant `<ApplicationStatusCard>` (par offre)
- Composant `<IntermediariesMap>` (utilise F11 `MapBlock`)
- Refactor `pages/dashboard.vue`
- Refactor `pages/reports/index.vue` : tabs ESG + Carbon
- Bouton "Rapport Carbone PDF" sur `pages/carbon/results.vue`
- Composable `useDashboard.ts` étendu
- Dark mode

### Base de données

- Pas de nouvelle table
- Lien F11 (MapBlock) requiert que `intermediaries.lat` et `intermediaries.lon` soient peuplés (via F09 admin)
- Lien F17 pour facteurs sourcés dans rapport carbone

## Critères d'acceptation

- [ ] Dashboard affiche 1 card par application (granularité par Offre)
- [ ] Carte UEMOA avec markers intermédiaires actifs sur dashboard
- [ ] Scores ESG/carbon/credit cliquables vers sources (F01)
- [ ] Endpoint `POST /api/reports/carbon/{id}/generate` fonctionnel
- [ ] PDF carbone généré avec 9 sections + annexe sources
- [ ] Page `/reports` avec onglets ESG + Carbon
- [ ] Tool `generate_carbon_report` fonctionnel
- [ ] Test E2E : 3 applications actives → 3 cards distinctes sur dashboard
- [ ] Test E2E : générer rapport carbone → PDF téléchargeable avec sources cliquables
- [ ] Couverture tests ≥ 80 %

## Risques & garde-fous

- **Risque** : trop de cards sur dashboard si user a 10 applications. **Garde-fou** : limite 5 cards visibles, "voir tout" → page applications complète.
- **Risque** : carte vide si aucun intermédiaire actif. **Garde-fou** : message "Vous n'avez pas encore d'intermédiaire actif" + lien vers catalogue.
- **Risque** : génération PDF carbone lente (matplotlib + WeasyPrint = ~5s). **Garde-fou** : génération asynchrone, notification quand prêt, déjà fait pour ESG.
- **Risque** : intermediaries n'ont pas de coordonnées (lat/lon). **Garde-fou** : F09 admin saisit progressivement, fallback sur capitale du country.
