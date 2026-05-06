# ESG Mefali - Fonctionnalités Complètes

## Vision du Projet

**Nom proposé :** ESG Mefali / Conseiller ESG IA

**Pitch :** Une plateforme conversationnelle IA qui démocratise l'accès à la finance durable pour les PME africaines francophones en combinant analyse de conformité ESG, conseil en financement vert et scoring de crédit alternatif.

---

## Architecture Technique

### Stack Technologique
- **Frontend :** Nuxt 4 + Composition API + Pinia (state management) + TailwindCSS + gsap + toast-ui/editor + chart.js + LangGraph, avec LangChain en couche utilitaire + etc...
- **Backend :** FastAPI (Python)
- **LLM :** Claude API (Anthropic) via OpenRouter(afin de pouvoir changer facilement)
- **Base de données :** PostgreSQL + pgvector (embeddings)
- **Stockage documents :** stockage local ( MinIO / S3 plus tard)
- **File d'attente :** traitement synchrone ( Redis + Celery  plus tard)

---

## Module 1 : Agent Conversationnel Principal

### 1.1 Interface de Chat Multimodale
- Chat en langage naturel en français (et langues locales plus tard)
- Support vocal (speech-to-text) pour les utilisateurs moins à l'aise avec l'écrit
- Historique des conversations persistant
- Mode guidé pour les nouveaux utilisateurs

### 1.2 Profilage Intelligent de l'Entreprise
- Questions conversationnelles pour comprendre l'activité
- Extraction automatique des informations clés :
  - Secteur d'activité (agriculture, énergie, recyclage, transport, etc.)
  - Taille de l'entreprise (CA, effectifs)
  - Localisation géographique
  - Pratiques environnementales actuelles
  - Structure de gouvernance
- Création d'un profil entreprise enrichi au fil des conversations

### 1.3 Mémoire Contextuelle
- Rappel des échanges précédents
- Suivi de l'évolution de l'entreprise dans le temps
- Suggestions proactives basées sur l'historique

---

## Module 2 : Analyseur de Conformité ESG

### 2.1 Upload et Analyse de Documents
- Upload de documents (PDF, images, Word, Excel)
- OCR intégré pour les documents scannés
- Extraction intelligente des informations via Claude :
  - Statuts juridiques
  - Rapports d'activité
  - Factures et justificatifs
  - Contrats fournisseurs
  - Politiques internes

### 2.2 Grille d'Évaluation ESG Contextualisée
- **Environnement (E) :**
  - Gestion des déchets et recyclage
  - Consommation énergétique
  - Émissions carbone estimées
  - Utilisation des ressources naturelles
  - Impact sur la biodiversité locale

- **Social (S) :**
  - Conditions de travail
  - Égalité homme/femme
  - Formation des employés
  - Impact communautaire
  - Santé et sécurité

- **Gouvernance (G) :**
  - Transparence financière
  - Structure de décision
  - Éthique des affaires
  - Conformité réglementaire
  - Lutte anti-corruption

### 2.3 Scoring ESG Dynamique
- Score global sur 100 points
- Scores détaillés par pilier (E, S, G)
- Benchmarking sectoriel (comparaison avec d'autres PME du secteur)
- Évolution du score dans le temps
- Badges et certifications virtuelles

### 2.4 Rapport de Conformité Généré
- Rapport PDF automatique en français
- Visualisations graphiques (radar charts, barres de progression)
- Identification des points forts
- Liste priorisée des lacunes à combler
- Conformité aux taxonomies vertes africaines (UEMOA, BCEAO)

---

## Module 3 : Conseiller en Financement Vert

### 3.1 Base de Données des Financements
- **Fonds internationaux :**
  - Fonds Vert pour le Climat (GCF)
  - Fonds pour l'Environnement Mondial (FEM)
  - Fonds d'Adaptation
  - etc (évolutif)

- **Institutions régionales :**
  - BOAD (Banque Ouest-Africaine de Développement)
  - BAD (Banque Africaine de Développement)
  - BIDC (Banque d'Investissement CEDEAO)
  - etc (évolutif)

- **Programmes nationaux :**
  - Fonds National pour l'Environnement (Côte d'Ivoire)
  - Lignes de crédit vert des banques locales
  - etc (évolutif)

- **Marchés carbone :**
  - Crédits carbone volontaires
  - Programmes REDD+
  - Gold Standard, Verra
  - etc (évolutif)

### 3.2 Matching Intelligent Projet-Financement
- Analyse de l'éligibilité automatique
- Score de compatibilité pour chaque fonds
- Explication des critères manquants
- Recommandations personnalisées
- Alertes sur les nouveaux appels à projets

### 3.3 Générateur de Dossiers de Candidature
- Templates pré-remplis pour chaque fonds
- Génération automatique des sections narratives
- Suggestions de formulation adaptées aux critères
- Checklist des documents requis
- Export en formats compatibles (Word, PDF)

### 3.4 Simulateur de Financement
- Estimation des montants éligibles
- Calcul du retour sur investissement vert
- Projection de l'impact environnemental
- Timeline estimée du processus

---

## Module 4 : Calculateur d'Empreinte Carbone

### 4.1 Questionnaire Conversationnel Simplifié
- Questions adaptées au contexte africain
- Exemples concrets et unités locales
- Catégories principales :
  - Énergie (électricité, générateurs, gaz)
  - Transport (véhicules, livraisons)
  - Déchets (volumes, traitement)
  - Achats (matières premières, fournitures)

### 4.2 Calcul et Visualisation
- Empreinte carbone annuelle estimée (tCO2e)
- Répartition par source d'émission
- Comparaison avec moyennes sectorielles
- Évolution mensuelle/annuelle

### 4.3 Plan de Réduction
- Recommandations priorisées par impact
- Estimation des économies financières
- Actions quick-wins vs long terme
- Suivi des objectifs de réduction

---

## Module 5 : Scoring de Crédit Vert Alternatif

### 5.1 Collecte de Données Non-Conventionnelles
- **Intégration Mobile Money :**
  - Analyse des flux (avec consentement)
  - Régularité des transactions
  - Volume d'activité

- **Données déclaratives enrichies :**
  - Questionnaire sur les pratiques
  - Photos de l'exploitation (analysées par IA)
  - Témoignages clients/fournisseurs

- **Données publiques :**
  - Présence sur les réseaux sociaux
  - Avis et recommandations
  - Participation à des programmes verts

### 5.2 Algorithme de Scoring Hybride
- Score de solvabilité (0-100)
- Score d'impact vert (0-100)
- Score combiné pondéré
- Explication transparente des facteurs

### 5.3 Passerelle Institutions Financières
- API pour partage sécurisé du score (avec consentement)
- Partenariats avec IMF et banques locales
- Certification du score par la plateforme
- Historique et évolution du score

---

## Module 6 : Plan d'Action et Accompagnement

### 6.1 Générateur de Feuille de Route
- Plan d'action personnalisé sur 6-12-24 mois
- Étapes concrètes et atteignables
- Ressources et outils recommandés
- Estimation des coûts et bénéfices

### 6.2 Système de Suivi et Rappels (cron)
- Notifications pour les échéances
- Rappels pour les actions planifiées
- Célébration des progrès (gamification)
- Ajustement dynamique du plan

### 6.3 Bibliothèque de Ressources
- Guides pratiques ESG en français
- Modèles de documents (politiques, procédures)
- Formations vidéo courtes
- FAQ contextualisées

---

## Module 7 : Tableau de Bord Entreprise

### 7.1 Dashboard Principal
- Vue synthétique des scores
- Graphiques d'évolution
- Prochaines actions recommandées
- Statut des candidatures aux financements

### 7.2 Rapports et Exports
- Rapport ESG complet téléchargeable
- Rapport carbone
- Attestation de scoring
- Historique des analyses

### 7.3 Multi-utilisateurs
- Gestion des accès (admin, collaborateur, lecteur)
- Historique des actions par utilisateur
- Commentaires et notes internes

---

## Module 8 : Extension Chrome — Accompagnement sur les Sites de Fonds

### 8.1 Détection Automatique des Fonds
- Détection intelligente du site de fonds visité (BOAD, GCF, BAD, AFD/SUNREF, etc.)
- Observation SPA (Single Page Application) pour suivre la navigation
- Bandeau de notification discret informant l'utilisateur qu'un fonds compatible a été détecté
- Support des patterns d'URL configurables par fonds

### 8.2 Pré-remplissage Intelligent des Formulaires
- Remplissage automatique des champs à partir du profil entreprise
- Suggestions IA contextuelles pour chaque champ (descriptions de projet, motivations, justifications)
- Remplissage séquentiel animé ("Tout remplir") pour visualiser le processus
- Code couleur des champs : vert (auto-rempli), bleu (suggéré par IA), orange (à remplir manuellement)

### 8.3 Panneau Latéral de Guidage
- Guide pas-à-pas intégré au navigateur (side panel)
- Composants dédiés : barre de progression, navigateur d'étapes, aide par champ
- Checklist documentaire : liste des pièces justificatives requises par fonds
- Mini-chat IA contextuel pour poser des questions en temps réel pendant le remplissage

### 8.4 Suivi des Candidatures
- Création automatique d'une candidature dès la détection d'un fonds
- Sauvegarde de la progression entre les sessions
- Tableau de bord des candidatures en cours dans le popup
- Détail de chaque candidature avec statut et étapes restantes

### 8.5 Notifications et Rappels
- Alertes d'échéances (J-30, J-7, J-1 avant date limite)
- Rappels pour les candidatures inactives (3+ jours sans activité)
- Déduplication intelligente des notifications
- Cycle d'alarmes automatique (vérification toutes les 6h)

### 8.6 Recommandations de Fonds
- Suggestions de fonds compatibles basées sur le profil et le score ESG
- Score de compatibilité pour chaque fonds recommandé
- Accès direct au site du fonds depuis l'extension

### 8.7 Multilingue
- Interface disponible en français et en anglais
- Internationalisation via chrome.i18n
- Français comme langue par défaut

---

## Fonctionnalités Différenciantes pour le Hackathon

### Innovation 1 : Approche Conversationnelle Native
- Pas de formulaires complexes : tout se fait par le chat
- L'IA guide l'utilisateur pas à pas
- Accessible aux personnes peu familières avec le numérique

### Innovation 2 : Contextualisation Africaine Profonde
- Critères ESG adaptés aux réalités locales
- Prise en compte du secteur informel
- Langues francaise
- Références aux réglementations UEMOA/CEDEAO

### Innovation 3 : Scoring de Crédit Vert Inclusif
- Résout le problème de l'exclusion bancaire
- Plus l'entreprise est verte, meilleur est son accès au crédit
- Crée un cercle vertueux : inclusion + transition écologique

### Innovation 4 : Génération Automatique de Dossiers
- Gain de temps considérable pour les PME
- Qualité professionnelle des documents
- Augmente les chances de succès des candidatures

### Innovation 5 : Approche Holistique
- Une seule plateforme pour tout : diagnostic, financement, suivi
- Cohérence entre les modules
- Parcours utilisateur fluide

---

## ODD Ciblés

1. **ODD 8** - Travail décent et croissance économique
2. **ODD 9** - Industrie, innovation et infrastructure
3. **ODD 10** - Inégalités réduites (inclusion financière)
4. **ODD 12** - Consommation et production responsables
5. **ODD 13** - Mesures relatives à la lutte contre les changements climatiques
6. **ODD 17** - Partenariats pour la réalisation des objectifs

---

## Roadmap de Développement (Hackathon)

### Phase 1
- Tout developper dès la phase 1

---

## Métriques d'Impact à Présenter

- Nombre de PME accompagnées (simulation)
- Montant de financements verts accessibles
- Réduction potentielle des émissions CO2
- Temps économisé vs consultant traditionnel
- Coût par PME accompagnée vs tarif consultant

---

## Points Clés pour le Jury

1. **Problème réel et urgent** : Les PME africaines sont exclues de la finance verte
2. **Solution concrète et actionnable** : Pas juste de l'information, mais des dossiers prêts à soumettre
3. **Technologie appropriée** : Le LLM rend accessible ce qui était réservé aux consultants
4. **Impact mesurable** : Métriques claires sur l'inclusion et le climat
5. **Scalabilité** : Applicable à toute la zone francophone africaine
6. **Équipe engagée** : Vision claire et roadmap réaliste
