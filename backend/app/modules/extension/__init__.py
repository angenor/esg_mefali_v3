"""Module Extension Chrome MV3 (F24).

Expose un sous-routeur ``/api/extension/v1/*`` avec 4 endpoints :
- ``POST /auth/exchange`` — échange identifiants → access+refresh tokens scope=extension
- ``GET /me/profile-snapshot`` — profil minimal entreprise + 3 derniers projets
- ``POST /detect`` — matching url → offre publiée correspondante
- ``GET /applications/active`` — candidatures actives (statuts non finaux)
"""
