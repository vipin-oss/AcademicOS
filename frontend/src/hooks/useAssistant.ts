"use client";

/**
 * Academic Intelligence Assistant data hook (mirror useSettings / useProductivity).
 *
 * Loads the AI Home payload once with `refresh()`; `ask` posts a question and
 * folds the returned exchange into the open thread; `openConversation` /
 * `newConversation` / `backToHome` switch the workspace view; rename / pin /
 * delete refresh the home payload silently afterwards.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { isAbortError, toErrorMessage } from "@/lib/api/client";
import {
  askQuestion,
  createConversation,
  deleteConversation,
  getAssistantHome,
  getConversation,
  listConversations,
  updateConversation,
} from "@/lib/api/assistant";
import type {
  AskResult,
  AssistantConversation,
  AssistantHome,
  ConversationDetail,
} from "@/types";

const HISTORY_PAGE_SIZE = 50;

export function useAssistant() {
  const [home, setHome] = useState<AssistantHome | null>(null);
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [thread, setThread] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const aliveRef = useRef(true);

  const loadHome = useCallback(async (signal?: AbortSignal, silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [payload, history] = await Promise.all([
        getAssistantHome(signal ? { signal } : undefined),
        listConversations(1, HISTORY_PAGE_SIZE, signal ? { signal } : undefined),
      ]);
      if (aliveRef.current) {
        setHome(payload);
        setConversations(history.items);
      }
    } catch (err) {
      if (isAbortError(err)) return;
      if (aliveRef.current) {
        setError(toErrorMessage(err, "Could not load the assistant home."));
      }
    } finally {
      if (!silent && aliveRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    const controller = new AbortController();
    void loadHome(controller.signal);
    return () => {
      aliveRef.current = false;
      controller.abort();
    };
  }, [loadHome]);

  const refresh = useCallback(
    (options?: { silent?: boolean }) => {
      void loadHome(undefined, options?.silent ?? false);
    },
    [loadHome],
  );

  /** Fold a returned exchange into the open thread (append the pair). */
  const foldExchange = useCallback((result: AskResult) => {
    setThread((prev) =>
      prev && prev.conversation.id === result.conversation.id
        ? {
            conversation: result.conversation,
            messages: [...prev.messages, result.user_message, result.assistant_message],
          }
        : {
            conversation: result.conversation,
            messages: [result.user_message, result.assistant_message],
          },
    );
  }, []);

  const ask = useCallback(
    async (question: string): Promise<AskResult | null> => {
      const cleaned = question.trim();
      if (!cleaned || sending) return null;
      setSending(true);
      setError(null);
      try {
        const result = await askQuestion(cleaned, thread?.conversation.id ?? null);
        if (!aliveRef.current) return result;
        foldExchange(result);
        void loadHome(undefined, true);
        return result;
      } catch (err) {
        if (!isAbortError(err) && aliveRef.current) {
          setError(toErrorMessage(err, "The assistant could not answer that."));
        }
        return null;
      } finally {
        if (aliveRef.current) setSending(false);
      }
    },
    [sending, thread?.conversation.id, foldExchange, loadHome],
  );

  const openConversation = useCallback(
    async (id: string) => {
      setThreadLoading(true);
      setError(null);
      try {
        const detail = await getConversation(id);
        if (aliveRef.current) setThread(detail);
      } catch (err) {
        if (!isAbortError(err) && aliveRef.current) {
          setError(toErrorMessage(err, "Could not open that conversation."));
        }
      } finally {
        if (aliveRef.current) setThreadLoading(false);
      }
    },
    [],
  );

  const backToHome = useCallback(() => setThread(null), []);

  const newConversation = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      const created = await createConversation();
      if (aliveRef.current) setThread({ conversation: created, messages: [] });
      void loadHome(undefined, true);
    } catch (err) {
      if (!isAbortError(err) && aliveRef.current) {
        setError(toErrorMessage(err, "Could not start a conversation."));
      }
    }
  }, [loadHome]);

  const rename = useCallback(
    async (id: string, title: string): Promise<boolean> => {
      try {
        const updated = await updateConversation(id, { title });
        setThread((prev) =>
          prev && prev.conversation.id === updated.id
            ? { ...prev, conversation: { ...prev.conversation, ...updated } }
            : prev,
        );
        void loadHome(undefined, true);
        return true;
      } catch (err) {
        if (!isAbortError(err) && aliveRef.current) {
          setError(toErrorMessage(err, "Could not rename the conversation."));
        }
        return false;
      }
    },
    [loadHome],
  );

  const togglePin = useCallback(
    async (conversation: AssistantConversation): Promise<void> => {
      try {
        const updated = await updateConversation(conversation.id, {
          pinned: !conversation.pinned,
        });
        setThread((prev) =>
          prev && prev.conversation.id === updated.id
            ? { ...prev, conversation: { ...prev.conversation, ...updated } }
            : prev,
        );
        void loadHome(undefined, true);
      } catch (err) {
        if (!isAbortError(err) && aliveRef.current) {
          setError(toErrorMessage(err, "Could not update the pin."));
        }
      }
    },
    [loadHome],
  );

  const remove = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        await deleteConversation(id);
        setThread((prev) => (prev && prev.conversation.id === id ? null : prev));
        void loadHome(undefined, true);
        return true;
      } catch (err) {
        if (!isAbortError(err) && aliveRef.current) {
          setError(toErrorMessage(err, "Could not delete the conversation."));
        }
        return false;
      }
    },
    [loadHome],
  );

  return {
    home,
    conversations,
    thread,
    loading,
    threadLoading,
    sending,
    error,
    refresh,
    ask,
    openConversation,
    backToHome,
    newConversation,
    rename,
    togglePin,
    remove,
  };
}
