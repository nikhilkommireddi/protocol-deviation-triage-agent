import type {
  AuditEvent,
  CapaStatus,
  DeviationSubmission,
  ExtractedFields,
  ManagedSite,
  ManagedUser,
  ReferenceData,
  ReviewSubmission,
  SiteCreateInput,
  SiteUpdateInput,
  TriageResult,
  UserInput,
} from "./types";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export function submitReport(submission: DeviationSubmission): Promise<TriageResult> {
  return request<TriageResult>("/reports", {
    method: "POST",
    body: JSON.stringify(submission),
  });
}

export async function extractFromPdf(file: File): Promise<ExtractedFields> {
  const formData = new FormData();
  formData.append("file", file);

  // No Content-Type header here -- the browser sets multipart/form-data
  // with the correct boundary itself; setting it manually breaks the upload.
  const response = await fetch(`${API_BASE_URL}/reports/extract-pdf`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`PDF extraction failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<ExtractedFields>;
}

export function listReports(): Promise<TriageResult[]> {
  return request<TriageResult[]>("/reports");
}

export function getReport(reportId: string): Promise<TriageResult> {
  return request<TriageResult>(`/reports/${reportId}`);
}

export function reviewReport(
  reportId: string,
  submission: ReviewSubmission,
): Promise<TriageResult> {
  return request<TriageResult>(`/reports/${reportId}/review`, {
    method: "POST",
    body: JSON.stringify(submission),
  });
}

export function updateCapaActionsStatus(
  reportId: string,
  actionsStatus: boolean[],
  actorName?: string,
  actorRole?: string,
): Promise<TriageResult> {
  return request<TriageResult>(`/reports/${reportId}/capa-actions`, {
    method: "POST",
    body: JSON.stringify({
      actions_status: actionsStatus,
      actor_name: actorName,
      actor_role: actorRole,
    }),
  });
}

export function getAuditTrail(reportId: string): Promise<AuditEvent[]> {
  return request<AuditEvent[]>(`/reports/${reportId}/audit`);
}

export function updateCapaStatus(
  reportId: string,
  status: CapaStatus,
  actorName?: string,
  actorRole?: string,
): Promise<TriageResult> {
  return request<TriageResult>(`/reports/${reportId}/capa-status`, {
    method: "POST",
    body: JSON.stringify({ status, actor_name: actorName, actor_role: actorRole }),
  });
}

export function getReferenceData(): Promise<ReferenceData> {
  return request<ReferenceData>("/reference");
}

export function listUsers(): Promise<ManagedUser[]> {
  return request<ManagedUser[]>("/users");
}

export function createUser(input: UserInput): Promise<ManagedUser> {
  return request<ManagedUser>("/users", { method: "POST", body: JSON.stringify(input) });
}

export function updateUser(userId: string, input: UserInput): Promise<ManagedUser> {
  return request<ManagedUser>(`/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteUser(userId: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/users/${userId}`, { method: "DELETE" });
}

export function listSites(): Promise<ManagedSite[]> {
  return request<ManagedSite[]>("/sites");
}

export function createSite(input: SiteCreateInput): Promise<ManagedSite> {
  return request<ManagedSite>("/sites", { method: "POST", body: JSON.stringify(input) });
}

export function updateSite(siteId: string, input: SiteUpdateInput): Promise<ManagedSite> {
  return request<ManagedSite>(`/sites/${siteId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteSite(siteId: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/sites/${siteId}`, { method: "DELETE" });
}
