import axios, { AxiosError } from 'axios';
import type { ApiError, CreateJobResponse, JobDetailResponse, StoresResponse } from '../types/leadImport';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 60000,
});

export function getApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error?: ApiError }>;
    return axiosError.response?.data?.error || {
      code: 'REQUEST_FAILED',
      message: '请求失败，请检查后端服务是否可用',
    };
  }
  return { code: 'UNKNOWN_ERROR', message: '发生未知错误' };
}

export async function createJob(
  file: File,
  remark?: string,
  forceStoreCode?: string
): Promise<CreateJobResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (remark) formData.append('remark', remark);
  if (forceStoreCode) formData.append('force_store_code', forceStoreCode);

  const response = await api.post<CreateJobResponse>('/leads/import', formData);
  return response.data;
}

export async function getJobDetail(jobId: string): Promise<JobDetailResponse> {
  const response = await api.get<JobDetailResponse>(`/leads/import/jobs/${jobId}`);
  return response.data;
}

export async function downloadFile(jobId: string): Promise<Blob> {
  const response = await api.get(`/leads/import/jobs/${jobId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}

export async function getStores(): Promise<StoresResponse> {
  const response = await api.get<StoresResponse>('/leads/import/stores');
  return response.data;
}

export { api };
