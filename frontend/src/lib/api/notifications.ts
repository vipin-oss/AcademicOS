/**
 * Notification API client for AcademicOS.
 *
 * Provides methods to list, count, mark-read, and delete notifications.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export interface Notification {
  id: string;
  user_id: string;
  notification_type: string;
  title: string;
  message: string;
  action_url?: string;
  is_read: boolean;
  created_at?: string;
  read_at?: string;
}

export interface UnreadCount {
  count: number;
}

function authHeaders(): HeadersInit {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Fetch notifications for the current user.
 */
export async function fetchNotifications(
  limit = 50,
  unreadOnly = false,
): Promise<Notification[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (unreadOnly) params.set("unread_only", "true");

  const res = await fetch(`${API_BASE}/notifications?${params}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch notifications: ${res.status}`);
  return res.json();
}

/**
 * Get unread notification count.
 */
export async function fetchUnreadCount(): Promise<number> {
  const res = await fetch(`${API_BASE}/notifications/count`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch unread count: ${res.status}`);
  const data: UnreadCount = await res.json();
  return data.count;
}

/**
 * Mark a single notification as read.
 */
export async function markNotificationRead(
  notificationId: string,
): Promise<boolean> {
  const res = await fetch(
    `${API_BASE}/notifications/${notificationId}/read`,
    {
      method: "PUT",
      headers: authHeaders(),
    },
  );
  if (!res.ok) throw new Error(`Failed to mark notification read: ${res.status}`);
  const data = await res.json();
  return data.success;
}

/**
 * Mark all notifications as read.
 */
export async function markAllNotificationsRead(): Promise<number> {
  const res = await fetch(`${API_BASE}/notifications/read-all`, {
    method: "PUT",
    headers: authHeaders(),
  });
  if (!res.ok)
    throw new Error(`Failed to mark all notifications read: ${res.status}`);
  const data = await res.json();
  return data.count;
}

/**
 * Delete a notification.
 */
export async function deleteNotification(
  notificationId: string,
): Promise<boolean> {
  const res = await fetch(
    `${API_BASE}/notifications/${notificationId}`,
    {
      method: "DELETE",
      headers: authHeaders(),
    },
  );
  if (!res.ok)
    throw new Error(`Failed to delete notification: ${res.status}`);
  const data = await res.json();
  return data.success;
}
