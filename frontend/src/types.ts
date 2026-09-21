export type UserRole = "site_coordinator" | "cra" | "quality_reviewer" | "administrator";

export interface DemoUser {
  name: string;
  role: UserRole;
  siteId?: string;
}

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

export interface SupervisorPlan {
  run_protocol_investigation: boolean;
  run_site_history: boolean;
  reasoning: string;
}

export interface ProtocolFindings {
  relevant: boolean;
  summary: string;
  citation: string;
  material_safety_change: boolean;
}

export interface HistoryFindings {
  prior_count: number;
  pattern_detected: boolean;
  summary: string;
}

export interface Adjudication {
  final_category: string;
  confidence: number;
  overridden: boolean;
  override_reason: string;
  classifier_category: string;
}

export interface Verification {
  passes: boolean;
  issues: string[];
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
  supervisor_plan: SupervisorPlan | null;
  protocol_findings: ProtocolFindings | null;
  history_findings: HistoryFindings | null;
  adjudication: Adjudication | null;
  capa_guidance: CapaGuidance | null;
  memo: Memo | null;
  verification: Verification | null;
  capa_actions_status: boolean[] | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export type ReviewDecision = "approved" | "rejected";

export interface ReviewSubmission {
  memo: Memo;
  status: ReviewDecision;
}

export interface ReferenceData {
  labels_markdown: string;
  capa_guidance: Record<string, CapaGuidance>;
}
