test cette feature avec `agent-browser --headed`

`claude --dangerously-skip-permissions`

Email: `amadou@ecosolaire.sn`
Mot de passe: `TestPass123!`

docker compose up -d postgres



Champ	Valeur
URL	http://localhost:3000
Email	mamadou.kone@ecoplast-ci.com
Mot de passe	EcoPlast2025!

merge la branche actuelle dans main, j'ai déjà commité

Après cette correction, relancer les 45 tests avec la cible : 42/45 minimum (93%).
Les 3 seuls échecs tolérés : 2.1 (upload OCR), 3.4 (interruption/reprise si non implémenté), un edge case.




Très bien ! Voici les alternatives à Entrée express que je vous recommande, classées de la plus adaptée à votre profil à la moins adaptée :

---

**1. Programme Mobilité francophone (ma recommandation n°1)**

C'est la voie la plus simple et la plus adaptée à votre situation. Ce programme permet aux employeurs canadiens (hors Québec) de vous embaucher **sans avoir besoin d'une Évaluation de l'impact sur le marché du travail (EIMT)**, ce qui simplifie énormément le processus. Le statut est actuellement **Ouvert**, les frais sont de seulement **155 $**, et c'est un permis de travail temporaire qui peut ensuite mener à la résidence permanente.

Pourquoi c'est idéal pour vous : vous êtes francophone natif, ingénieur logiciel (secteur STIM très demandé), et vous travaillez déjà pour une organisation canadienne (l'OIF basée au Québec). Il vous suffit de trouver un employeur canadien **hors Québec** prêt à vous embaucher. Votre expérience avec l'OIF et vos missions internationales (COP) sont un excellent atout.

**2. Programme pilote d'immigration dans les communautés francophones**

Ce programme offre directement la **résidence permanente** à des travailleurs francophones qualifiés dans des communautés rurales francophones hors Québec. Il vous faut une offre d'emploi d'un employeur désigné dans une communauté participante. C'est une voie vers la résidence permanente plus directe qu'Entrée express.

**3. Questionnaire d'orientation du gouvernement**

Il y a aussi sur la page un lien très utile : « Répondez à quelques questions et découvrez les autres programmes d'immigration du Canada ». Ce questionnaire officiel analyse votre situation et vous propose les programmes les plus adaptés parmi tous ceux disponibles (pas seulement ceux pour francophones).

---

**Mon conseil concret :** Commencez par le **Programme Mobilité francophone**. Avec votre profil d'ingénieur logiciel francophone, concentrez-vous sur la recherche d'un employeur au Canada (hors Québec) — en Ontario, au Nouveau-Brunswick, au Manitoba, ou en Alberta par exemple. Les entreprises tech canadiennes recrutent activement et l'avantage de ce programme est que l'employeur n'a pas besoin de passer par l'EIMT, ce qui le rend plus attractif pour eux aussi.

Souhaitez-vous que j'ouvre la page d'admissibilité du Programme Mobilité francophone ou le questionnaire d'orientation ?



Les feature dévéloppés par speckit sembles fonctionner partiellement et je ne suis pas sùr de la qualité d'implementation, qu'est-ce que je peux faire avec BMAD pour regler celà, des reviews ? ou quoi ?
de plus j'ai de nouvelles évolution pour la plateforme:
- il arrive qu'un entrepreneurs veuil un financement pour un projet, il désir donc postuler avec un projet et non pas avec l'enreprise(je paraphrase). 
- vu la demande précédente, un profil devrait peut-etre etre dynamique: infos entreprise, infos projet(il semblerait qu'un meme projet peut avoir des dossiers différent selon le fond où on veut postuler)
-  Esg Mefali doit pouvoir monter un dossier pour demander le financement d'un projet particulier, sans exclure qu'on doit aussi pouvoir monter un dossier pour demander le financement de l'entreprise
- il semblerait que les Criteres ESG soit aussi relatif, il va falloir creuser
- Esg Mefali doit pouvoir faire une étude d’impact du projet d'une entreprise ou de l’entreprise
- le Tableau de bord peut etre plus expressif, plus grafique

Comment gerer tout ca avec BMAD