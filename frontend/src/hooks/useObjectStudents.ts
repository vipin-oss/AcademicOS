"use client";

import { useCallback, useEffect, useState } from "react";
import { toErrorMessage } from "@/lib/api/client";
import { listStudentsByObject } from "@/lib/api/students";
import type { StudentResponse } from "@/types";

export interface UseObjectStudentsResult {
  students: StudentResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** The object lens: students linked to one Object (e.g. as supervisees). */
export function useObjectStudents(objectId: string | null): UseObjectStudentsResult {
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [loading, setLoading] = useState(Boolean(objectId));
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!objectId) {
      setStudents([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);

    listStudentsByObject(objectId, { signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setStudents(response.items);
      })
      .catch((err) => {
        if (!active || err?.name === "AbortError") return;
        setError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [objectId, reloadToken]);

  const refresh = useCallback(() => setReloadToken((token) => token + 1), []);

  return { students, loading, error, refresh };
}
