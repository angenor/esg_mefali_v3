// frontend/app/lib/guided-tours/registry.ts

import type { GuidedTourDefinition } from '~/types/guided-tour'

/** Duree par defaut du compte a rebours avant navigation (en secondes) */
export const DEFAULT_ENTRY_COUNTDOWN = 8

/**
 * Registre extensible des parcours guides pre-definis.
 * Convention ids : show_[module]_[page] en snake_case.
 * Convention selectors : [data-guide-target="xxx"] uniquement.
 * Les placeholders {{...}} sont interpoles par useGuidedTour (Story 5.1).
 *
 * Pour ajouter un parcours : ajouter une entree ici + les data-guide-target
 * correspondants sur les composants cibles. Zero modification du moteur.
 */
export const tourRegistry = {
  show_esg_results: {
    id: 'show_esg_results',
    steps: [
      {
        route: '/esg/results',
        selector: '[data-guide-target="esg-score-circle"]',
        popover: {
          title: 'Score ESG global',
          description: 'Votre score ESG est de {{esg_score}}/100. Ce cercle montre votre performance environnementale, sociale et de gouvernance.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="esg-strengths-badges"]',
        popover: {
          title: 'Points forts identifiés',
          description: 'Vos meilleures pratiques ESG sont affichées ici. Elles valorisent votre entreprise auprès des bailleurs.',
          side: 'right',
        },
      },
      {
        selector: '[data-guide-target="esg-recommendations"]',
        popover: {
          title: 'Recommandations personnalisées',
          description: 'Ces actions prioritaires vous permettront d\'améliorer votre score et d\'accéder à davantage de financements verts.',
          side: 'top',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-esg-link"]',
      popover: {
        title: 'Résultats ESG',
        description: 'Cliquez ici pour voir votre évaluation ESG détaillée.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/esg/results',
    },
  },

  show_carbon_results: {
    id: 'show_carbon_results',
    steps: [
      {
        route: '/carbon/results',
        selector: '[data-guide-target="carbon-donut-chart"]',
        popover: {
          title: 'Répartition de vos émissions',
          description: 'Votre empreinte est de {{total_tco2}} tCO2e. Ce graphique montre la répartition par catégorie — {{top_category}} représente {{top_category_pct}}% du total.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="carbon-benchmark"]',
        popover: {
          title: 'Comparaison sectorielle',
          description: 'Votre position par rapport à la moyenne de votre secteur ({{sector}}).',
          side: 'right',
        },
      },
      {
        selector: '[data-guide-target="carbon-reduction-plan"]',
        popover: {
          title: 'Plan de réduction',
          description: 'Les actions recommandées pour réduire votre empreinte carbone, classées par impact.',
          side: 'top',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-carbon-link"]',
      popover: {
        title: 'Résultats Empreinte Carbone',
        description: 'Cliquez ici pour voir vos résultats détaillés.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/carbon/results',
    },
  },

  show_financing_catalog: {
    id: 'show_financing_catalog',
    steps: [
      {
        route: '/financing',
        selector: '[data-guide-target="financing-fund-list"]',
        popover: {
          title: 'Catalogue des fonds disponibles',
          description: '{{matched_count}} fonds de financement vert sont compatibles avec votre profil et votre secteur d\'activité.',
          side: 'bottom',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-financing-link"]',
      popover: {
        title: 'Financements verts',
        description: 'Cliquez ici pour explorer les fonds disponibles.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/financing',
    },
  },

  show_credit_score: {
    id: 'show_credit_score',
    steps: [
      {
        route: '/credit',
        selector: '[data-guide-target="credit-score-gauge"]',
        popover: {
          title: 'Score de crédit vert',
          description: 'Votre score de crédit alternatif est de {{credit_score}}/100. Il combine solvabilité traditionnelle et impact environnemental.',
          side: 'bottom',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-credit-link"]',
      popover: {
        title: 'Score Crédit Vert',
        description: 'Cliquez ici pour consulter votre score de crédit alternatif.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/credit',
    },
  },

  show_action_plan: {
    id: 'show_action_plan',
    steps: [
      {
        route: '/action-plan',
        selector: '[data-guide-target="action-plan-timeline"]',
        popover: {
          title: 'Votre plan d\'action',
          description: '{{active_actions}} actions prioritaires sur 6, 12 et 24 mois pour améliorer votre performance ESG.',
          side: 'bottom',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-action-plan-link"]',
      popover: {
        title: 'Plan d\'action',
        description: 'Cliquez ici pour voir votre feuille de route personnalisée.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/action-plan',
    },
  },

  show_reports_carbon: {
    id: 'show_reports_carbon',
    steps: [
      {
        route: '/reports?tab=carbon',
        selector: '[data-guide-target="reports-tab-carbon"]',
        popover: {
          title: 'Onglet Carbone',
          description: 'Vous êtes sur l\'onglet Carbone. Votre rapport « {{report_filename}} » apparaît ici dès qu\'il est prêt.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="reports-list-carbon"]',
        popover: {
          title: 'Vos rapports carbone',
          description: 'Téléchargez, prévisualisez ou supprimez vos rapports depuis cette liste.',
          side: 'top',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-reports-link"]',
      popover: {
        title: 'Mes rapports',
        description: 'Votre rapport carbone vient d\'être généré. Cliquez ici pour le retrouver.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/reports?tab=carbon',
    },
  },

  show_reports_esg: {
    id: 'show_reports_esg',
    steps: [
      {
        route: '/reports?tab=esg',
        selector: '[data-guide-target="reports-tab-esg"]',
        popover: {
          title: 'Onglet ESG',
          description: 'Vous êtes sur l\'onglet ESG. Votre rapport « {{report_filename}} » apparaît ici dès qu\'il est prêt.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="reports-list-esg"]',
        popover: {
          title: 'Vos rapports ESG',
          description: 'Téléchargez, prévisualisez ou supprimez vos rapports depuis cette liste.',
          side: 'top',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-reports-link"]',
      popover: {
        title: 'Mes rapports',
        description: 'Votre rapport ESG vient d\'être généré. Cliquez ici pour le retrouver.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/reports?tab=esg',
    },
  },

  show_dashboard_overview: {
    id: 'show_dashboard_overview',
    steps: [
      {
        route: '/dashboard',
        selector: '[data-guide-target="dashboard-esg-card"]',
        popover: {
          title: 'Synthèse ESG',
          description: 'Score ESG : {{esg_score}}/100. Un aperçu rapide de vos axes d\'amélioration.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="dashboard-carbon-card"]',
        popover: {
          title: 'Synthèse Carbone',
          description: 'Empreinte totale : {{total_tco2}} tCO2e. Les catégories principales de vos émissions.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="dashboard-credit-card"]',
        popover: {
          title: 'Synthèse Crédit',
          description: 'Score crédit vert : {{credit_score}}/100. Les facteurs clés de votre évaluation.',
          side: 'bottom',
        },
      },
      {
        selector: '[data-guide-target="dashboard-financing-card"]',
        popover: {
          title: 'Synthèse Financements',
          description: '{{matched_count}} opportunités de financement vert identifiées pour votre entreprise.',
          side: 'bottom',
        },
      },
    ],
    entryStep: {
      selector: '[data-guide-target="sidebar-dashboard-link"]',
      popover: {
        title: 'Tableau de bord',
        description: 'Cliquez ici pour accéder à votre tableau de bord complet.',
        countdown: DEFAULT_ENTRY_COUNTDOWN,
      },
      targetRoute: '/dashboard',
    },
  },
} satisfies Record<string, GuidedTourDefinition>
