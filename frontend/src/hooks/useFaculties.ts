"use client";

import { useMemo } from "react";

import { listFaculty } from "@/lib/api/faculty";
import { DEFAULT_FACULTY_PAGE_SIZE } from "@/lib/faculty/constants";
import { usePagedList } from "@/hooks/usePagedList";
import type {
  FacultyEmploymentType,
  FacultyResponse,
  ResearchObjectStatus,
} from "@/types";

export interface UseFacultiesOptions {
  pageSize?: number;
  /** Raw (undebounced) search text — the hook debounces it internally. */
  search?: string;
  searchDelay?: number;
  /** PART 7 server-side filters (`null` disables each). */
  department?: string | null;
  designation?: string | null;
  employmentType?: FacultyEmploymentType | null;
  status?: ResearchObjectStatus | null;
}

export interface UseFacultiesResult {
  items: FacultyResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  isSearching: boolean;
  searchActive: boolean;
  filterActive: boolean;
  setPage: (page: number) => void;
  refresh: () => void;
}

interface FacultyFilters {
  department?: string | null;
  designation?: string | null;
  employmentType?: FacultyEmploymentType | null;
  status?: ResearchObjectStatus | null;
}

/**
 * Faculty directory list state — thin wrapper over the shared
 * `usePagedList` framework (R6): server pagination + debounced server-side
 * search + server-side filters + refresh. The exported interface is
 * unchanged; only the internals now delegate to the framework.
 */
export function useFaculties(options: UseFacultiesOptions = {}): UseFacultiesResult {
  const {
    pageSize = DEFAULT_FACULTY_PAGE_SIZE,
    search = "",
    searchDelay = 300,
    department = null,
    designation = null,
    employmentType = null,
    status = null,
  } = options;

  const params = useMemo<FacultyFilters>(
    () => ({
      department: department?.trim() || null,
      designation: designation?.trim() || null,
      employmentType: employmentType ?? null,
      status: status ?? null,
    }),
    [department, designation, employmentType, status],
  );

  return usePagedList<FacultyResponse, FacultyFilters>({
    pageSize,
    search,
    searchDelay,
    filterValues: [department, designation, employmentType, status],
    params,
    fetcher: (request, signal) => listFaculty(request, { signal }),
  });
}
