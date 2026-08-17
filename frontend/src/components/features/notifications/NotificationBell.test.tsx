/**
 * Tests for the NotificationBell component.
 *
 * Covers: rendering, unread badge, dropdown toggle, mark-read, mark-all-read.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import NotificationBell from "./NotificationBell";

// Mock the API modules
vi.mock("@/lib/api/notifications", () => ({
  fetchNotifications: vi.fn().mockResolvedValue([
    {
      id: "n1",
      user_id: "u1",
      notification_type: "document_analyzed",
      title: "Document analyzed",
      message: "Your paper was analyzed successfully.",
      action_url: "/documents/doc1",
      is_read: false,
      created_at: new Date().toISOString(),
    },
    {
      id: "n2",
      user_id: "u1",
      notification_type: "conflicts_detected",
      title: "Conflicts detected",
      message: "2 fields need resolution.",
      action_url: "/documents/doc2",
      is_read: true,
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
  ]),
  fetchUnreadCount: vi.fn().mockResolvedValue(1),
  markNotificationRead: vi.fn().mockResolvedValue(true),
  markAllNotificationsRead: vi.fn().mockResolvedValue(2),
}));

vi.mock("@/hooks/useNotifications", () => ({
  useNotifications: vi.fn(() => ({
    unreadCount: 1,
    loading: false,
    refresh: vi.fn(),
  })),
}));

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the bell button", () => {
    render(<NotificationBell />);
    const button = screen.getByLabelText(/notifications/i);
    expect(button).toBeTruthy();
  });

  it("shows unread badge when there are unread notifications", () => {
    render(<NotificationBell />);
    // The badge should show "1"
    const badge = screen.getByText("1");
    expect(badge).toBeTruthy();
  });

  it("opens dropdown on click", async () => {
    render(<NotificationBell />);
    const button = screen.getByLabelText(/notifications/i);

    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Notifications")).toBeTruthy();
    });
  });

  it("shows notification items in dropdown", async () => {
    render(<NotificationBell />);
    const button = screen.getByLabelText(/notifications/i);

    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Document analyzed")).toBeTruthy();
      expect(screen.getByText("Conflicts detected")).toBeTruthy();
    });
  });

  it("shows mark all read button when there are unread notifications", async () => {
    render(<NotificationBell />);
    const button = screen.getByLabelText(/notifications/i);

    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Mark all read")).toBeTruthy();
    });
  });

  it("closes dropdown on outside click", async () => {
    render(<NotificationBell />);
    const button = screen.getByLabelText(/notifications/i);

    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Notifications")).toBeTruthy();
    });

    // Click outside
    fireEvent.mouseDown(document.body);

    await waitFor(() => {
      expect(screen.queryByText("Document analyzed")).toBeNull();
    });
  });
});
