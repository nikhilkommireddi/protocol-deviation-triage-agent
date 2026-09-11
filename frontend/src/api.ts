import type {
  DeviationSubmission,
  ReviewSubmission,
  TriageResult,
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
