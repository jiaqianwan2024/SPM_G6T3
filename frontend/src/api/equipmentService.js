import { createServiceClient } from "./axiosClient";

const axiosClient = createServiceClient("equipment");

export const getEquipmentList = () => axiosClient.get("/equipment");

export const getEquipmentQueue = () => axiosClient.get("/equipment/queue");

export const getUpcomingEquipmentQueue = (params) => axiosClient.get("/equipment/upcoming", { params });

// SPM-58: Technical Support's home screen, every section in one reply.
export const getTechDashboard = () => axiosClient.get("/equipment/dashboard");

export const getEquipment = (equipmentId) => axiosClient.get(`/equipment/${equipmentId}`);

export const createEquipment = (body) => axiosClient.post("/equipment", body);

export const updateEquipment = (equipmentId, body) => axiosClient.patch(`/equipment/${equipmentId}`, body);

export const checkEquipmentAvailability = (body) => axiosClient.post("/equipment/availability", body);

export const getEquipmentRequests = () => axiosClient.get("/equipment/requests");

export const getEventReservations = (eventId) =>
  axiosClient.get("/equipment/reservations", { params: { eventId } });

export const getReservationSummary = (eventId) =>
  axiosClient.get("/equipment/reservations/summary", { params: { eventId } });

export const getEquipmentReservations = (equipmentId) =>
  axiosClient.get(`/equipment/${equipmentId}/reservations`);

export const createEquipmentRequest = (body) => axiosClient.post("/equipment/requests", body);

export const refineEquipmentRequest = (requestId, body) =>
  axiosClient.patch(`/equipment/requests/${requestId}/details`, body);

export const reviewEquipmentRequest = (requestId, body) =>
  axiosClient.post(`/equipment/requests/${requestId}/review`, body);

export const reserveEquipmentRequest = (requestId) =>
  axiosClient.post(`/equipment/requests/${requestId}/reserve`);

export const markEquipmentRequestUnavailable = (requestId, body) =>
  axiosClient.post(`/equipment/requests/${requestId}/unavailable`, body);

export const getEquipmentActivityLog = (equipmentId) =>
  axiosClient.get(`/equipment/${equipmentId}/activity-log`);

// SPM-77: technical support's answers to a line that cannot be fully met, and the coordinator's.
export const recordPartialFulfilment = (requestId, reservedQuantity, reason) =>
  axiosClient.post(`/equipment/requests/${requestId}/partial`, { reservedQuantity, reason });

export const acceptEquipmentShortfall = (requestId) =>
  axiosClient.post(`/equipment/requests/${requestId}/accept-shortfall`);

export const completeEquipmentReview = (requestId) =>
  axiosClient.post(`/equipment/requests/${requestId}/complete-review`);

// The coordinator amends an unavailable or partly met line and sends it back for review.
export const resubmitEquipmentRequest = (requestId, quantity) =>
  axiosClient.patch(`/equipment/requests/${requestId}`, { resubmit: true, quantity });

// SPM-78 and SPM-86: technical support change, release, or re-confirm a held reservation.
export const adjustEquipmentReservation = (reservationId, quantity) =>
  axiosClient.patch(`/equipment/reservations/${reservationId}`, { quantity });

export const releaseEquipmentReservation = (reservationId, reason) =>
  axiosClient.post(`/equipment/reservations/${reservationId}/release`, { reason });

export const reconfirmEquipmentReservation = (reservationId) =>
  axiosClient.post(`/equipment/reservations/${reservationId}/reconfirm`);
