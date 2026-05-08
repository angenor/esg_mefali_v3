// F24 — Wrapper chrome.i18n avec fallback FR (utile en tests / dev sans MV3).

const FR_FALLBACKS: Record<string, string> = {
  app_name: "ESG Mefali",
  popup_login_title: "Connexion à votre espace ESG Mefali",
  popup_login_email: "Adresse email",
  popup_login_password: "Mot de passe",
  popup_login_submit: "Se connecter",
  popup_login_error_invalid:
    "Identifiants invalides. Vérifiez votre email et votre mot de passe.",
  popup_login_error_network:
    "Connexion impossible. Vérifiez votre connexion internet.",
  popup_logout: "Se déconnecter",
  popup_logged_out_title: "Connectez-vous d'abord",
  popup_register_link: "Pas encore de compte ? Créer un compte",
  dashboard_title: "Mes candidatures actives",
  dashboard_empty_state: "Aucune candidature active pour le moment.",
  dashboard_open_app: "Ouvrir le dossier",
  overlay_offer_detected: "Offre détectée",
  overlay_view_button: "Voir cette offre",
  overlay_close_button: "Fermer",
  overlay_source_link: "Voir la source",
  loading: "Chargement…",
};

export function t(key: string): string {
  if (typeof chrome !== "undefined" && chrome.i18n?.getMessage) {
    const v = chrome.i18n.getMessage(key);
    if (v) return v;
  }
  return FR_FALLBACKS[key] ?? key;
}
