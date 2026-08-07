/** Annotations API client tests (Sprint M10): paths, methods, payloads. */
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  api: { get: mocks.get, post: mocks.post, put: mocks.put, delete: mocks.del },
}));

import {
  createAnnotation,
  deleteAnnotation,
  getExtractedText,
  listAnnotations,
  updateAnnotation,
} from "@/lib/api/annotations";

beforeEach(() => {
  mocks.get.mockReset();
  mocks.post.mockReset();
  mocks.put.mockReset();
  mocks.del.mockReset();
  mocks.get.mockResolvedValue({});
  mocks.post.mockResolvedValue({});
  mocks.put.mockResolvedValue({});
  mocks.del.mockResolvedValue(undefined);
});

describe("annotations client", () => {
  it("lists annotations for a document", async () => {
    await listAnnotations("obj:document:1");
    expect(mocks.get).toHaveBeenCalledWith("/documents/obj:document:1/annotations", undefined);
  });

  it("creates a highlight with rects + text", async () => {
    await createAnnotation("obj:document:1", "highlight", 2, {
      rects: [{ x0: 0, y0: 0, x1: 9, y1: 9 }],
      text: "wave",
    });
    expect(mocks.post).toHaveBeenCalledWith(
      "/documents/obj:document:1/annotations",
      {
        annotation_type: "highlight",
        page: 2,
        payload: { rects: [{ x0: 0, y0: 0, x1: 9, y1: 9 }], text: "wave" },
      },
      undefined,
    );
  });

  it("updates an annotation", async () => {
    await updateAnnotation("ann-1", { page: 3, payload: { text: "moved" } });
    expect(mocks.put).toHaveBeenCalledWith(
      "/documents/annotations/ann-1",
      { page: 3, payload: { text: "moved" } },
      undefined,
    );
  });

  it("deletes an annotation", async () => {
    await deleteAnnotation("ann-1");
    expect(mocks.del).toHaveBeenCalledWith("/documents/annotations/ann-1", undefined);
  });

  it("fetches the extracted text", async () => {
    await getExtractedText("obj:document:1");
    expect(mocks.get).toHaveBeenCalledWith("/documents/obj:document:1/extracted-text", undefined);
  });
});
