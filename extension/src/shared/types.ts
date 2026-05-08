// F24 — Types miroir des schemas Pydantic backend (copie manuelle MVP).

export interface AuthExchangeResponse {
  access_token: string;
  refresh_token: string;
  scope: "extension";
  expires_in: number;
}

export interface DetectResponse {
  offer_id: string;
  offer_name: string;
  source_id: string | null;
  confidence: number;
}

export interface ProjectSnapshotItem {
  id: string;
  name: string;
  status: string;
}

export interface ProfileSnapshot {
  sector: string | null;
  country: string | null;
  projects: ProjectSnapshotItem[];
}

export interface ActiveApplicationItem {
  id: string;
  offer_name: string;
  status: string;
  status_label_fr: string;
  updated_at: string;
  deep_link: string;
}

export interface AuthState {
  token: string | null;
  email: string | null;
  isAuthenticated: boolean;
}

export type DetectMessage = {
  type: "DETECT_URL";
  url: string;
};

export type DetectMessageResponse =
  | { ok: true; match: DetectResponse | null }
  | { ok: false; error: string };
