export interface DeviationSubmission {
  protocol_id: string;
  site_id: string;
  subject_id: string;
  deviation_date: string;
  discovery_date: string;
  text: string;
}

export interface ExtractedFields {
  protocol_id: string;
  site_id: string;
  subject_id: string;
  deviation_date: string;
  discovery_date: string;
  text: string;
}

export interface CapaGuidance {
  routing_team: string;
  regulatory_reference: string;
  required_capa_elements: string[];
}

export interface Memo {
  summary: string;
  root_cause_narrative: string;
  regulatory_citation: string;
  recommended_capa_actions: string[];
  requires_expedited_reporting: boolean;
  responsible_party: string;
  target_resolution_date: string;
  reviewer_note?: string;
}

export interface TriageResult {
  report_id: string;
  protocol_id: string;
  site_id: string;
  subject_id: string;
  deviation_date: string;
  discovery_date: string;
  text: string;
  category: string | null;
  confidence: number | null;
  capa_guidance: CapaGuidance | null;
  memo: Memo | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export type ReviewDecision = "approved" | "rejected";

export interface ReviewSubmission {
  memo: Memo;
  status: ReviewDecision;
}
