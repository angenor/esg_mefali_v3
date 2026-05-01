# Réponses - Hackathon Francophone IA (Green Open Lab / IFDD)

---

## Pitch (200 mots max)

ESG Mefali est une plateforme conversationnelle d'IA qui démocratise l'accès à la finance verte pour les PME francophones africaines.

En Afrique francophone, 90 % des PME sont exclues des fonds verts : dossiers complexes, consultants inabordables (5 000–20 000 $), barrières linguistiques. ESG Mefali résout ce problème grâce à un agent conversationnel intelligent qui guide les entrepreneurs en français.

La plateforme combine : un scoring ESG multi-référentiel (BCEAO, IFC, GCF, etc) adapté aux réalités ouest-africaines, un calculateur d'empreinte carbone contextualisé, un matching intelligent vers 10 fonds verts régionaux et internationaux, un crédit scoring alternatif intégrant mobile money et pratiques vertes, et la génération automatique de dossiers PDF prêts à soumettre.

Une extension Chrome accompagne les PME directement sur les sites de fonds, avec pré-remplissage automatique et suggestions IA pour chaque champ.

Stack technique : Vue 3 + FastAPI + PostgreSQL/pgvector + Claude (OpenRouter). Architecture RAG hybride (SQL + recherche sémantique), 20+ skills dynamiques, streaming SSE.

Notre ambition : rendre chaque PME africaine capable de financer sa transition verte, sans intermédiaire coûteux.

---

## Thématique principale

Finance Durable (avec des composantes Climat et Employabilité verte)

---

## Problème

Les PME francophones africaines sont massivement exclues de la finance verte. Trois barrières les bloquent :

1. Complexité ESG — Les référentiels (IFC, GCF, BCEAO) sont techniques, volumineux et en anglais. Sans consultant spécialisé (5 000–20 000 $), une PME ne peut ni évaluer sa conformité, ni identifier ses lacunes.

2. Opacité du financement vert — Il existe des dizaines de fonds (BOAD, BAD, GCF, AFD/SUNREF...) avec des critères d'éligibilité différents. Les PME ne savent pas lesquels existent, ne savent pas si elles sont éligibles, et abandonnent face à la complexité des dossiers.

3. Invisibilité financière — Sans historique de crédit formel, même les PME vertueuses sur le plan environnemental ne peuvent pas accéder aux prêts bancaires. Leurs bonnes pratiques ESG ne sont ni mesurées ni valorisées.

Résultat : moins de 10 % des financements climat en Afrique atteignent les PME, alors qu'elles représentent 80 % de l'emploi et sont les premières impactées par le changement climatique.

---

## Comment utilisez-vous l'intelligence artificielle concrètement ?

L'IA est au cœur de chaque fonctionnalité :

- Agent conversationnel (Claude via OpenRouter) — Un LLM orchestre 20+ skills dynamiques via function calling. Il collecte les données par dialogue naturel (pas de formulaires), exécute les calculs, et synthétise les résultats en français. Boucle agentique multi-tours (max 10 itérations) avec streaming SSE.

- RAG hybride (SQL + pgvector) — Les documents entreprise et les descriptions de fonds sont découpés en chunks, vectorisés (Voyage AI, 1024 dimensions) et indexés avec HNSW dans PostgreSQL. La recherche combine filtrage SQL (secteur, pays, montant) et similarité cosinus sémantique pour un matching précis des fonds.

- Scoring ESG par NLP — L'agent extrait les réponses quantitatives (pourcentages, kWh, tonnes) et qualitatives (pratiques déclarées) du langage naturel, les mappe sur les grilles multi-référentielles, et calcule les scores pondérés par pilier (E/S/G).

- Crédit scoring alternatif — Modèle hybride combinant score de solvabilité et score d'impact vert, intégrant données ESG, tendances carbone et transactions mobile money.

- Suggestion IA pour formulaires (extension Chrome) — Le LLM génère des contenus adaptés (descriptions de projet, motivations) pour chaque champ de candidature, en contexte avec le profil entreprise et le fonds ciblé.

- Analyse documentaire — OCR (pytesseract) + extraction PDF/Word + chunking intelligent pour analyser les documents entreprise et pré-remplir les dossiers.

---

## En quoi votre approche se distingue par rapport aux solutions existantes ? (200 mots max)

Les solutions ESG existantes (Refinitiv, Sustainalytics, CDP) ciblent les grandes entreprises occidentales avec des abonnements à 10 000+ $/an, des interfaces en anglais et des référentiels inadaptés à l'Afrique.

ESG Mefali se distingue sur 5 axes :

1. Conversationnel-first — Zéro formulaire. L'agent IA pose les bonnes questions, extrait les données du dialogue naturel, et enrichit le profil progressivement. Accessible aux entrepreneurs peu alphabétisés grâce à la saisie vocale.

2. Multi-référentiel contextualisé — Supporte simultanément les cadres BCEAO (UEMOA), IFC et GCF, avec des critères et pondérations adaptés par secteur et pays africain. Pas de grille unique imposée.

3. Du diagnostic à l'action — Ne s'arrête pas au score : génère des plans de réduction carbone chiffrés (coût, ROI en XOF), assemble les dossiers PDF, et guide le remplissage des formulaires en ligne via l'extension Chrome.

4. Crédit scoring inclusif — Valorise les pratiques vertes dans l'accès au crédit, intégrant mobile money et données alternatives pour les PME sans historique bancaire formel.

5. Architecture ouverte — Skills dynamiques en base de données, modèle LLM interchangeable (Claude/GPT/Mistral via OpenRouter), extensible sans redéploiement.

---

## Stade de développement

MVP — Infrastructure complète déployée via Docker, 20 tables en base, authentification, chat IA avec streaming, scoring ESG, calculateur carbone, matching de fonds, extension Chrome fonctionnelle avec 27 tests unitaires. Prêt pour démonstration.

---

## À quels Objectifs de Développement Durable contribuez-vous ?

- ODD 8 — Travail décent et croissance économique : accès au capital pour les PME vertes, promotion de l'emploi vert
- ODD 9 — Industrie, innovation et infrastructure : adoption de technologies propres par les PME africaines
- ODD 10 — Inégalités réduites : démocratisation de la finance verte, inclusion des non-bancarisés via le crédit scoring alternatif
- ODD 12 — Consommation et production responsables : suivi des déchets, promotion de l'économie circulaire
- ODD 13 — Mesures relatives à la lutte contre les changements climatiques : quantification de l'empreinte carbone, plans de réduction, canalisation du financement climat vers les PME
- ODD 17 — Partenariats pour la réalisation des objectifs : connexion PME ↔ fonds internationaux ↔ banques

---

## Qu'attendez-vous du programme de mentorat ?

Nous attendons du programme de mentorat un accompagnement sur trois axes :

1. Validation terrain et go-to-market — Confronter notre MVP à des retours d'utilisateurs réels (PME ouest-africaines), affiner le produit, et définir une stratégie de déploiement pays par pays en commençant par la Côte d'Ivoire et le Sénégal.

2. Partenariats stratégiques — Être mis en relation avec des acteurs clés : institutions financières régionales (BOAD, BCEAO), organisations de microfinance, incubateurs africains, et bailleurs de fonds verts pour des pilotes concrets.

3. Modèle économique et financement — Structurer un modèle de revenus viable (freemium pour PME, licences pour institutions financières, commissions sur fonds débloqués) et préparer un dossier de levée de fonds pour passer du MVP à l'échelle.

Le coaching sur l'IA responsable nous intéresse particulièrement pour assurer la transparence de nos algorithmes de scoring et éviter les biais dans le crédit scoring alternatif.

---

## Lien drive de votre vidéo Pitch (2 min)

(À compléter)

---

## Lien Drive de votre Deck PDF

(À compléter)





# Script Vidéo Pitch — ESG Mefali (2 minutes)

## Conseils avant d'enregistrer

- **Format** : Filme-toi face caméra (webcam ou téléphone en mode paysage)
- **Fond** : Neutre ou avec ton écran d'ordi visible derrière toi
- **Tenue** : Correcte mais pas trop formelle (chemise, polo)
- **Ton** : Passionné, naturel, pas robotique — tu parles d'un problème qui te tient à cœur
- **Durée cible** : 1min50 (garde 10s de marge)
- **Astuce** : Tu peux alterner entre toi face caméra et des captures d'écran de la plateforme

---

## Structure et texte à dire

### ACCROCHE — Face caméra (0:00 – 0:15)

> « Bonjour, je suis [TON NOM], createur d'ESG Mefali.
>
> Saviez-vous que moins de 10 % des financements climat en Afrique atteignent les PME ? Pourtant, elles représentent 80 % de l'emploi sur le continent.
>
> Le problème n'est pas le manque de fonds. C'est que les PME n'y ont pas accès. »

---

### LE PROBLÈME — Face caméra (0:15 – 0:40)

> « Aujourd'hui, une PME ivoirienne ou sénégalaise qui veut accéder à un fonds vert fait face à trois murs :
>
> **Premier mur** : les référentiels ESG sont complexes, techniques, souvent en anglais. Pour s'y conformer, il faut un consultant à 5 000 voire 20 000 dollars — impensable pour une PME.
>
> **Deuxième mur** : il existe des dizaines de fonds — BOAD, GCF, BAD, AFD — mais personne ne sait lequel correspond à son profil, ni comment remplir le dossier.
>
> **Troisième mur** : sans historique de crédit formel, pas de prêt bancaire. Même si l'entreprise a d'excellentes pratiques environnementales. »

---

### LA SOLUTION — Montrer l'écran / démo (0:40 – 1:20)

> « ESG Mefali change la donne. C'est un conseiller ESG virtuel, accessible en français, qui accompagne les PME de A à Z. »

*[Montre l'interface du chat]*

> « L'entrepreneur dialogue simplement avec l'agent IA. Pas de formulaires compliqués. L'agent pose les bonnes questions, calcule le score ESG selon les référentiels africains — BCEAO, IFC, GCF — et identifie les fonds verts compatibles. »

*[Montre le dashboard avec les scores ESG]*

> « Il calcule aussi l'empreinte carbone, propose un plan de réduction chiffré en francs CFA, et génère les dossiers de candidature en PDF, prêts à soumettre. »

*[Montre l'extension Chrome si possible]*

> « Et notre extension Chrome va encore plus loin : elle accompagne l'entrepreneur directement sur le site du fonds, pré-remplit les formulaires et suggère les réponses grâce à l'IA. »

---

### LA TECH — Face caméra (1:20 – 1:35)

> « Techniquement, la plateforme repose sur une architecture RAG hybride : on combine recherche sémantique par vecteurs et filtrage SQL pour matcher précisément les PME avec les bons fonds. L'agent utilise Claude comme LLM avec plus de 20 skills dynamiques. Le tout tourne sur Vue 3, FastAPI et PostgreSQL avec pgvector. On est au stade MVP, fonctionnel et prêt pour démonstration. »

---

### L'AMBITION — Face caméra, regard caméra (1:35 – 1:55)

> « Notre vision : que chaque PME africaine puisse financer sa transition verte, sans intermédiaire coûteux. On cible d'abord la zone UEMOA — Côte d'Ivoire, Sénégal, Mali — avant de s'étendre à toute l'Afrique francophone.
>
> ESG Mefali, c'est la finance verte rendue accessible à ceux qui en ont le plus besoin. Merci. »

---

## Récapitulatif du timing

| Segment | Durée | Cumul | Ce que tu fais |
|---------|-------|-------|----------------|
| Accroche | 15s | 0:15 | Face caméra, ton accrocheur |
| Problème | 25s | 0:40 | Face caméra, 3 points clairs |
| Solution | 40s | 1:20 | Partage d'écran / captures de la plateforme |
| Tech | 15s | 1:35 | Face caméra, résumé technique rapide |
| Ambition | 20s | 1:55 | Face caméra, regard direct, conclusion forte |

---

## Checklist avant d'enregistrer

- [ ] La plateforme tourne (`docker compose up -d`) pour les captures
- [ ] Préparer 3-4 captures d'écran clés : chat, dashboard ESG, calculateur carbone, extension Chrome
- [ ] Tester le son (pas de bruit de fond)
- [ ] Répéter 2-3 fois à voix haute pour le timing
- [ ] Filmer en 1080p minimum
- [ ] Uploader sur Google Drive et mettre le lien en accès "Tous ceux qui ont le lien"

---
---

# Vidéo de Présentation — Phase 2 (1 minute)

> Contexte : projet retenu parmi les 10 finalistes. Cette vidéo est différente du pitch de 2 min déjà soumis. Elle doit couvrir : présentation personnelle/équipe, pays, nom du projet, description, groupe cible, problématique.

---

## Ce que tu dis (texte prêt à lire)

> « Bonjour, je suis Angenor N'GOUANDI, Ingénieur, Enseignant et formateur technique en Informatique. Originaire de Côte d'Ivoire. Je porte le projet ESG Mefali.
>
> ESG Mefali est une plateforme d'intelligence artificielle conversationnelle dédiée à la finance verte. Concrètement, c'est un agent IA en français qui aide les petites et moyennes entreprises africaines à comprendre les critères ESG, évaluer leur conformité, et monter leurs dossiers pour accéder aux fonds verts.
>
> On s'adresse aux PME de l'Afrique francophone, en priorité la zone UEMOA — Côte d'Ivoire, Sénégal, Mali — des entreprises qui ont la volonté de s'engager dans une démarche durable mais qui sont bloquées par le manque de moyens et d'accompagnement.
>
> La problématique est claire : moins de 10 % des financements climat en Afrique parviennent aux PME. Pourtant elles représentent 80 % de l'emploi. Les référentiels ESG sont complexes et en anglais, les consultants coûtent entre 5 000 et 20 000 dollars, et sans historique bancaire formel, pas de crédit. Des millions d'entrepreneurs sont tout simplement exclus de la transition verte.
>
> ESG Mefali existe pour changer ça. Merci. »

---

## Découpage timing

| Moment | Durée | Cumul | Ce que tu couvres |
|--------|-------|-------|-------------------|
| Présentation + Pays | 8s | 0:08 | Prénom, rôle, Côte d'Ivoire |
| Nom + Description du projet | 15s | 0:23 | ESG Mefali = agent IA finance verte |
| Groupe cible | 12s | 0:35 | PME UEMOA francophones |
| Problématique | 22s | 0:57 | Chiffres + 3 barrières |
| Fermeture | 3s | 1:00 | Phrase de conclusion |

---

## Conseils

- Parle naturellement, pas besoin de tout réciter mot pour mot — l'essentiel c'est de couvrir les 6 points
- Rythme calme et posé (1 min c'est court, ne pas se presser non plus)
- Regard caméra direct, fond neutre
- Répète 3-4 fois à voix haute pour caler le timing












>  Bonjour ! je suis Angenor N'GOUANDI — ingénieur, enseignant et formateur technique en informatique, basé en Côte d'Ivoire. Je suis le porteur du projet ESG Mefali.

> ESG Mefali, c'est Un agent conversationnel propulsé par l'intelligence artificielle, entièrement en français, pensé pour la finance verte. 

> Son rôle : accompagner les PME africaines pas à pas — de la compréhension des critères ESG au montage de leurs dossiers pour décrocher des financements verts. 

> Nortre solution va encore plus loins, une extension Chrome en dévéloppement accompagne l'entrepreneur directement sur les sites de fonds(BOAD, le GCF ou la BAD), et le guide en temps reel dans sont procesus de candidature.

> Notre cible ? Les PME d'Afrique francophone, les entrepreneurs motivés, prêts à s'engager dans le durable, mais qui se retrouvent seuls face à un mur.

> Et ce mur est bien réel. Moins de 10 % des financements climat en Afrique arrivent aux PME — alors qu'elles represente 80 % de l'emploi. Les référentiels ESG ? Complexes, en anglais. Les consultant Autour de 5 000 dollars.  Des millions d'entrepreneurs sont ainsi exclus de la transition verte.

> ESG Mefali est né pour briser cette barrière. Merci.  »
