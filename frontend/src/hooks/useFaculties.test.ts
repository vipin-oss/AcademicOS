import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listFaculty } from "@/lib/api/faculty";
import { useFaculties } from "./useFaculties";

/**
 * Pins the useFaculties -> usePagedList delegation (R6): the wrapper keeps
 * its public interface and forwards page/pageSize/q + the faculty filters
 * to the API, and the framework's result shape surfaces unchanged.
 */
vi.mock("@/lib/api/faculty", () => ({
  listFaculty: vi.fn(),
}));

const mockedListFaculty = vi.mocked(listFaculty);

describe("useFaculties", () => {
  beforeEach(() => {
    mockedListFaculty.mockReset();
    mockedListFaculty.mockResolvedValue({
      items: [{ id: "obj:faculty:1" }],
      total_count: 1,
    } as never);
  });

  it("fetches the directory with pagination and trimmed filters", async () => {
    const { result } = renderHook(() =>
      useFaculties({
        pageSize: 25,
        search: "  kumar ",
        department: "  physics ",
        designation: null,
        employmentType: "regular",
        status: "active",
      }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockedListFaculty).toHaveBeenCalledWith(
      {
        page: 1,
        pageSize: 25,
        q: "kumar",
        department: "physics",
        designation: null,
        employmentType: "regular",
        status: "active",
      },
      { signal: expect.any(AbortSignal) },
    );
    expect(result.current.items).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.searchActive).toBe(true);
    expect(result.current.filterActive).toBe(true);
  });

  it("exposes the framework's full result surface", async () => {
    const { result } = renderHook(() => useFaculties({ pageSize: 2 }));

    await waitFor(() => expect(result.current.loading).toBe(false));
    const r = result.current;
    expect(typeof r.setPage).toBe("function");
    expect(typeof r.refresh).toBe("function");
    expect(r.totalPages).toBe(1);
    expect(r.page).toBe(1);
    expect(r.pageSize).toBe(2);
    expect(r.error).toBeNull();
    expect(r.isSearching).toBe(false);
    expect(r.refreshing).toBe(false);
  });
});
