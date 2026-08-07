import { api } from './api';

export type NotificationType =
  'budget_ceiling' | 'negative_projection' | 'goal_hit' | 'reserve_progress';

export type Severity = 'info' | 'warning' | 'danger' | 'success';

export type Notification = {
  id: number;
  type: NotificationType;
  severity: Severity;
  title: string;
  message: string;
  read: boolean;
  reference_month: string | null;
  subject: string | null;
  created_at: string;
};

export type NotificationList = {
  items: Notification[];
  unread_count: number;
};

export function getNotifications() {
  return api.get<NotificationList>('/notifications');
}

export function markNotificationRead(id: number) {
  return api.patch<Notification>(`/notifications/${id}/read`, {});
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  info: '#85b7eb',
  success: '#5dcaa5',
  warning: '#e8a33d',
  danger: '#e85c4a',
};
