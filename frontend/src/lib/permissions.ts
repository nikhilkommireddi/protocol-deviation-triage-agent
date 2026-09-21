import type { DemoUser, UserRole } from "../types";

// Frontend-only demo role gating -- there is no backend auth behind this.
// Every existing API endpoint remains callable by anyone regardless of the
// role picked here. This exists to demo what a role-based UI would look
// like, not to secure anything.

export const DEMO_SITE_ID = "001";

export type Capability =
  | "intake"
  | "review"
  | "review.edit"
  | "review.decide"
  | "correct"
  | "correct.edit"
  | "analytics"
  | "safety"
  | "rules"
  | "subjects"
  | "admin";

export const ALL_ROLES: UserRole[] = [
  "site_coordinator",
  "cra",
  "quality_reviewer",
  "administrator",
];

export const CAPABILITY_LABELS: Record<Capability, string> = {
  intake: "Submit new deviations",
  review: "View Review Queue",
  "review.edit": "Edit / override classification",
  "review.decide": "Approve or reject",
  correct: "View CAPA tracking (Correct)",
  "correct.edit": "Check off CAPA actions",
  analytics: "View Analytics",
  safety: "View Safety Tracker",
  rules: "View Rule Catalog",
  subjects: "View Subjects",
  admin: "View Administration",
};

export const ROLE_CAPABILITIES: Record<UserRole, Capability[]> = {
  site_coordinator: ["intake", "review", "rules", "subjects"],
  cra: ["review", "review.edit", "correct", "analytics", "safety", "rules", "subjects"],
  quality_reviewer: [
    "review",
    "review.edit",
    "review.decide",
    "correct",
    "correct.edit",
    "analytics",
    "safety",
    "rules",
    "subjects",
  ],
  administrator: ["review", "correct", "analytics", "rules", "subjects", "admin"],
};

export function can(user: DemoUser | null, capability: Capability): boolean {
  if (!user) return false;
  return ROLE_CAPABILITIES[user.role].includes(capability);
}

export interface RoleInfo {
  role: UserRole;
  title: string;
  description: string;
  capabilities: string[];
}

export const ROLE_INFO: RoleInfo[] = [
  {
    role: "site_coordinator",
    title: "Site Coordinator",
    description: "Submits deviations at the site level and tracks their own site's history.",
    capabilities: [
      "Submit deviations",
      "Upload deviation PDFs",
      "View deviations belonging to their site",
      "View their site's history",
    ],
  },
  {
    role: "cra",
    title: "CRA / Clinical Operations",
    description: "Monitors assigned sites, reviews AI classifications, and tracks CAPA follow-through.",
    capabilities: [
      "View assigned sites",
      "View deviations",
      "Review AI classifications",
      "Override classifications",
      "Track CAPA",
      "View site history",
      "Generate reports",
    ],
  },
  {
    role: "quality_reviewer",
    title: "Quality Reviewer",
    description: "Final authority on classification and CAPA closure.",
    capabilities: [
      "Review deviations",
      "Review AI assessment",
      "Override AI classification",
      "Review/approve CAPA",
      "Close deviations",
      "View audit history",
    ],
  },
  {
    role: "administrator",
    title: "Administrator",
    description: "System oversight -- users, roles, and sites (read-only in this demo; see note on the Administration page).",
    capabilities: ["Manage users", "Manage roles", "Manage sites", "View system/audit information"],
  },
];
