/**
 * Entity Match API client for AcademicOS.
 *
 * Provides methods to confirm/reject entity matches and fetch pending matches.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export interface PendingMatch {
  target_doc_id: string;
  confidence: number;
  evidence: string;
  decision: string;
  created_at?: string;
}

export interface PendingMatchesResponse {
  document_id: string;
  pending_matches: PendingMatch[];
}

export interface MatchActionResponse {
  success: boolean;
  source_doc_id: string;
  target_doc_id: string;
  already_linked: boolean;
  error?: string;
}

function authHeaders(): HeadersInit {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Get pending entity matches for a document.
 */
export async function fetchPendingMatches(
  documentId: string,
): Promise<PendingMatchesResponse> {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(documentId)}/pending-matches`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(`Failed to fetch pending matches: ${res.status}`);
  return res.json();
}

/**
 * Confirm an entity match — creates a RELATED_TO relationship.
 */
export async function confirmEntityMatch(
  sourceDocId: string,
  targetDocId: string,
): Promise<MatchActionResponse> {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(sourceDocId)}/confirm-match/${encodeURIComponent(targetDocId)}`,
    {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    },
  );
  if (!res.ok) throw new Error(`Failed to confirm match: ${res.status}`);
  return res.json();
}

/**
 * Reject an entity match — persists rejection, no relationship created.
 */
export async function rejectEntityMatch(
  sourceDocId: string,
  targetDocId: string,
): Promise<MatchActionResponse> {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(sourceDocId)}/reject-match/${encodeURIComponent(targetDocId)}`,
    {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
    },
  );
  if (!res.ok) throw new Error(`Failed to reject match: ${res.status}`);
  return res.json();
}

/**
 * Get related documents for a document.
 */
export async function fetchRelatedDocuments(
  documentId: string,
): Promise<{ document_id: string; related: Array<{ document_id: string; title: string; object_type: string; relationship_kind: string }> }> {
  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(documentId)}/related`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(`Failed to fetch related documents: ${res.status}`);
  return res.json();
}
