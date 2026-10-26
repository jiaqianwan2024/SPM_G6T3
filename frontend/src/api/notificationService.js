import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("notification");

export const sendNotification = (to, subject, body) =>
  axiosClient.post("/notifications", { to, subject, body });

// The signed-in user's own in-app notifications, newest first, one page at a
// time. unreadOnly/page/pageSize all optional - the backend defaults match.
// bell: true leaves out what the user cleared from the bell (the full history does not pass it).
export const getNotifications = ({ unreadOnly, page, pageSize, bell } = {}) =>
  axiosClient.get("/notifications", {
    params: { unreadOnly, page, pageSize, bell },
  });

// For the bell badge - cheaper than fetching the list just to count it.
export const getUnreadNotificationCount = () => axiosClient.get("/notifications/unread-count");

export const markNotificationRead = (notificationId) =>
  axiosClient.post(`/notifications/${notificationId}/read`);

export const markAllNotificationsRead = () => axiosClient.post("/notifications/read-all");

// Hides one notification from the bell (and marks it read). Nothing is deleted.
export const clearNotification = (notificationId) => axiosClient.post(`/notifications/${notificationId}/clear`);

// Hides everything from the bell and marks it read. Nothing is deleted; See all still lists it.
export const clearAllNotifications = () => axiosClient.post("/notifications/clear-all");
