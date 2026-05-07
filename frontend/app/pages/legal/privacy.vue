<script setup lang="ts">
definePageMeta({ layout: 'public', auth: false })
</script>

<template>
  <article
    class="max-w-3xl mx-auto px-4 py-10 prose prose-sm dark:prose-invert"
  >
    <h1>Politique de confidentialité</h1>
    <p class="text-sm text-gray-500">Version v1.0 — dernière mise à jour : 7 mai 2026</p>

    <section>
      <h2>1. Responsable du traitement</h2>
      <p>
        ESG Mefali — Plateforme de finance durable pour les PME africaines
        francophones.<br />
        Contact privacy : <a href="mailto:privacy@esg-mefali.com">privacy@esg-mefali.com</a>.
      </p>
    </section>

    <section>
      <h2>2. Finalités et bases légales</h2>
      <ul>
        <li>
          <strong>Analyse profil entreprise</strong> (base : contrat) — pour
          vous proposer des financements adaptés à votre activité.
        </li>
        <li>
          <strong>Analyse IA des documents uploadés</strong> (base : contrat) —
          pour extraire automatiquement les informations ESG de vos pièces
          justificatives.
        </li>
        <li>
          <strong>Analyse Mobile Money</strong> (base : consentement explicite) —
          pour calculer un score crédit alternatif.
        </li>
        <li>
          <strong>Analyse photos d'exploitation</strong> (base : consentement
          explicite) — pour enrichir votre scoring crédit.
        </li>
        <li>
          <strong>Analyse données publiques</strong> (base : consentement
          explicite) — pour intégrer des avis et présence en ligne au scoring.
        </li>
        <li>
          <strong>Génération attestation crédit transmissible</strong> (base :
          contrat) — pour produire une attestation Ed25519 vérifiable destinée
          aux financeurs.
        </li>
        <li>
          <strong>Communications produit</strong> (base : consentement
          explicite) — pour vous informer des nouveautés (1 email/mois max).
        </li>
      </ul>
    </section>

    <section>
      <h2>3. Catégories de données collectées</h2>
      <ul>
        <li>Identité du représentant : email, nom complet.</li>
        <li>Profil entreprise : raison sociale, secteur, pays, taille.</li>
        <li>Documents uploadés : factures, états financiers, photos.</li>
        <li>
          Données métier : projets, candidatures, évaluations ESG, bilans
          carbone, scores crédit, attestations.
        </li>
        <li>
          Conversations chat avec l'assistant IA (historique des messages).
        </li>
        <li>
          Métadonnées techniques : IP, user-agent (uniquement pour audit
          sécurité).
        </li>
      </ul>
    </section>

    <section>
      <h2>4. Durée de conservation</h2>
      <ul>
        <li>
          Compte actif : tant que l'utilisateur n'a pas demandé la suppression.
        </li>
        <li>
          Compte programmé pour suppression : 30 jours (délai de grâce
          annulable).
        </li>
        <li>
          Audit log anonymisé après suppression : 6 ans (conformité légale et
          comptable).
        </li>
        <li>
          Backups : 30 jours (BDD), 90 jours (fichiers uploadés).
        </li>
      </ul>
    </section>

    <section>
      <h2>5. Sous-traitants</h2>
      <ul>
        <li>
          <strong>OpenRouter / Anthropic Claude API</strong> — fournisseur LLM,
          DPA en cours d'établissement, données envoyées anonymisées au maximum.
        </li>
        <li>
          <strong>exchangerate-api.com</strong> — taux de change USD pivot,
          aucune donnée personnelle transmise.
        </li>
        <li>
          <strong>Hébergeur</strong> (à confirmer en production : OVH /
          Scaleway / Africa Data Centres) — région Europe ou Afrique de l'Ouest
          uniquement.
        </li>
      </ul>
    </section>

    <section>
      <h2>6. Transferts hors UE / UEMOA</h2>
      <p>
        Les données sont hébergées en Europe ou en Afrique de l'Ouest selon le
        provider final. Aucune donnée n'est stockée sur des serveurs soumis au
        CLOUD Act US.
      </p>
    </section>

    <section>
      <h2>7. Vos droits</h2>
      <ul>
        <li>
          <strong>Droit d'accès (Art. 15 RGPD)</strong> : consulter votre
          inventaire et exporter vos données via
          <NuxtLink to="/mes-donnees">/mes-donnees</NuxtLink>.
        </li>
        <li>
          <strong>Droit de rectification (Art. 16)</strong> : modifier votre
          profil et vos consentements à tout moment.
        </li>
        <li>
          <strong>Droit à l'effacement (Art. 17)</strong> : supprimer votre
          compte (délai de grâce 30 jours).
        </li>
        <li>
          <strong>Droit à la portabilité (Art. 20)</strong> : exporter vos
          données en JSON structuré.
        </li>
        <li>
          <strong>Droit d'opposition (Art. 21)</strong> : révoquer un
          consentement granulaire à tout moment.
        </li>
      </ul>
    </section>

    <section>
      <h2>8. Comment exercer vos droits</h2>
      <p>
        La plupart des droits s'exercent en ligne via
        <NuxtLink to="/mes-donnees">/mes-donnees</NuxtLink>. Pour toute autre
        demande, contactez
        <a href="mailto:privacy@esg-mefali.com">privacy@esg-mefali.com</a>.
        Nous vous répondrons sous 30 jours conformément à l'Art. 12.3 du RGPD.
      </p>
    </section>

    <section>
      <h2>9. Coordonnées DPO</h2>
      <p>
        DPO formalisé : à nommer avant déploiement production. Contact
        temporaire :
        <a href="mailto:privacy@esg-mefali.com">privacy@esg-mefali.com</a>.
      </p>
    </section>

    <section>
      <h2>10. Historique des versions</h2>
      <ul>
        <li>v1.0 — 7 mai 2026 — Version initiale (lancement MVP F05).</li>
      </ul>
    </section>

    <p class="mt-8 text-xs text-gray-500">
      Cadre légal applicable : RGPD européen (UE 2016/679), loi ivoirienne
      2013-450, règlement UEMOA n°20/2010/CM/UEMOA, loi sénégalaise
      n°2008-12.
    </p>
  </article>
</template>
