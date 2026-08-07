/** Document viewer API client (Sprint M10) — annotations + extracted text. */
import { api, type RequestOptions } from "@/lib/api/client";
import type { AnnotationPayload, AnnotationType, DocumentAnnotation, ExtractedTextResponse } from "@/types";

/** `GET /documents/{id}/extracted-text` — the linked intake item's text. */
export function getExtractedText(
  documentId: string,
  options?: RequestOptions,
): Promise<ExtractedTextResponse> {
  return api.get<ExtractedTextResponse>(`/documents/${documentId}/extracted-text`, options);
}

/** `GET /documents/{id}/annotations` — page-ordered annotation list. */
export function listAnnotations(
  documentId: string,
  options?: RequestOptions,
): Promise<{ items: DocumentAnnotation[] }> {
  return api.get<{ items: DocumentAnnotation[] }>(`/documents/${documentId}/annotations`, options);
}

/** `POST /documents/{id}/annotations` — create an annotation. */
export function createAnnotation(
  documentId: string,
  annotationType: AnnotationType,
  page: number,
  payload: AnnotationPayload,
  options?: RequestOptions,
): Promise<DocumentAnnotation> {
  return api.post<DocumentAnnotation>(
    `/documents/${documentId}/annotations`,
    { annotation_type: annotationType, page, payload },
    options,
  );
}

/** `PUT /documents/annotations/{id}` — update page/payload. */
export function updateAnnotation(
  annotationId: string,
  changes: { page?: number; payload?: AnnotationPayload },
  options?: RequestOptions,
): Promise<DocumentAnnotation> {
  return api.put<DocumentAnnotation>(
    `/documents/annotations/${annotationId}`,
    { page: changes.page ?? null, payload: changes.payload ?? null },
    options,
  );
}

/** `DELETE /documents/annotations/{id}` — remove an annotation. */
export function deleteAnnotation(annotationId: string, options?: RequestOptions): Promise<void> {
  return api.delete<void>(`/documents/annotations/${annotationId}`, options);
}
