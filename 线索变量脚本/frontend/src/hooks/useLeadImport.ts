import { useCallback, useEffect, useRef, useState } from 'react';
import type { ApiError, ImportStatus, JobDetailResponse } from '../types/leadImport';
import { createJob, downloadFile, getApiError, getJobDetail } from '../api/leadImportClient';

const POLLING_INTERVAL_MS = 1800;
const TERMINAL_STATUSES: ImportStatus[] = ['completed', 'failed', 'need_confirmation'];

export function useLeadImport() {
  const [status, setStatus] = useState<ImportStatus>('idle');
  const [jobId, setJobId] = useState('');
  const [jobDetail, setJobDetail] = useState<JobDetailResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const pollingRef = useRef<number | null>(null);

  const clearPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const pollJob = useCallback(async (currentJobId: string) => {
    const detail = await getJobDetail(currentJobId);
    setJobDetail(detail);
    setStatus(detail.status);
    if (detail.error) setError(detail.error);
    if (TERMINAL_STATUSES.includes(detail.status)) clearPolling();
  }, [clearPolling]);

  const startPolling = useCallback((currentJobId: string) => {
    clearPolling();
    void pollJob(currentJobId);
    pollingRef.current = window.setInterval(() => {
      void pollJob(currentJobId).catch((err) => {
        setError(getApiError(err));
        setStatus('failed');
        clearPolling();
      });
    }, POLLING_INTERVAL_MS);
  }, [clearPolling, pollJob]);

  const uploadFile = useCallback(async (file: File, forceStoreCode?: string) => {
    setStatus('uploading');
    setError(null);
    try {
      const response = await createJob(file, undefined, forceStoreCode);
      setJobId(response.job_id);
      setStatus(response.status);
      startPolling(response.job_id);
    } catch (err) {
      setError(getApiError(err));
      setStatus('failed');
      clearPolling();
    }
  }, [clearPolling, startPolling]);

  const downloadTxt = useCallback(async () => {
    if (!jobId) return;
    try {
      const blob = await downloadFile(jobId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `lead-import-${jobId}.txt`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiError(err));
    }
  }, [jobId]);

  const reset = useCallback(() => {
    clearPolling();
    setStatus('idle');
    setJobId('');
    setJobDetail(null);
    setError(null);
  }, [clearPolling]);

  useEffect(() => clearPolling, [clearPolling]);

  return {
    status,
    setStatus,
    jobId,
    jobDetail,
    error,
    isPolling: pollingRef.current !== null,
    uploadFile,
    downloadTxt,
    reset,
  };
}
