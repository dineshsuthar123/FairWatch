import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

const flattenErrorDetail = (detail) => {
  if (detail == null) {
    return "";
  }

  if (Array.isArray(detail)) {
    return detail.map(flattenErrorDetail).filter(Boolean).join(" ");
  }

  if (typeof detail === "object") {
    if (detail.msg) {
      const location = Array.isArray(detail.loc)
        ? detail.loc.filter((part) => part !== "body").join(".")
        : "";
      return location ? `${location}: ${detail.msg}` : String(detail.msg);
    }

    return Object.values(detail).map(flattenErrorDetail).filter(Boolean).join(" ");
  }

  return String(detail);
};

const toErrorMessage = (error, fallbackMessage) =>
  flattenErrorDetail(error?.response?.data?.detail) ||
  flattenErrorDetail(error?.response?.data?.message) ||
  flattenErrorDetail(error?.response?.data) ||
  error?.message ||
  fallbackMessage;

export const getModels = async () => {
  const response = await api.get("/api/models");
  return response.data.models || [];
};

export const registerModel = async (payload) => {
  const response = await api.post("/api/models/register", payload);
  return response.data;
};

export const uploadDataset = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/api/upload/dataset", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
};

export const submitPredictions = async (payload) => {
  const response = await api.post("/api/predict", payload);
  return response.data;
};

export const getReports = async (modelId) => {
  const response = await api.get(`/api/reports/${modelId}`);
  return response.data.reports || [];
};

export const getLatestReport = async (modelId) => {
  const response = await api.get(`/api/reports/${modelId}/latest`);
  return response.data;
};

export const regenerateLatestExplanation = async (modelId) => {
  const response = await api.post(`/api/reports/${modelId}/latest/regenerate`);
  return response.data;
};

export const getAlerts = async (modelId) => {
  const response = await api.get(`/api/alerts/${modelId}`);
  return response.data.alerts || [];
};

export const resolveAlert = async (alertId) => {
  const response = await api.post(`/api/alerts/${alertId}/resolve`);
  return response.data;
};

export const injectDemoBias = async (modelId) => {
  const response = await api.post(`/api/demo/inject-bias`, null, {
    params: { model_id: modelId },
  });
  return response.data;
};

export const resetDemo = async (modelId) => {
  const response = await api.post(`/api/demo/reset`, null, {
    params: { model_id: modelId },
  });
  return response.data;
};

export const sendChatMessage = async (modelId, query) => {
  const response = await api.post(`/api/chat/${modelId}`, { query });
  return response.data;
};

export const withApiError = (error, fallbackMessage) => toErrorMessage(error, fallbackMessage);
