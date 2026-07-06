export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'need_confirmation';

export type ImportStatus =
  | 'idle'
  | 'file_selected'
  | 'uploading'
  | 'pending'
  | 'processing'
  | 'need_confirmation'
  | 'completed'
  | 'failed';

export interface ApiError {
  code: string;
  message: string;
  detail?: string;
}

export interface StoreInfo {
  store_code: string;
  store_name: string;
  city: string;
  brand: string;
  keywords?: string[];
  script_path?: string;
  folder_name?: string;
  call_mode?: string;
  enabled?: boolean;
}

export interface DetectedStore {
  store_code: string;
  store_name: string;
  confidence: number;
  matched_by: string[];
}

export interface CandidateStore {
  store_code: string;
  store_name: string;
  confidence: number;
}

export interface FileInfo {
  filename: string;
  size: number;
  saved_path?: string | null;
  format?: string;
}

export interface JobOutput {
  txt_file_path?: string | null;
  download_url?: string | null;
  txt_preview?: string;
}

export interface JobDetailResponse {
  job_id: string;
  status: JobStatus;
  detected_store: DetectedStore | null;
  candidate_stores: CandidateStore[];
  input_file: FileInfo;
  output: JobOutput;
  logs: string[];
  error: ApiError | null;
  created_at: string;
  updated_at: string;
}

export interface CreateJobResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface StoresResponse {
  stores: StoreInfo[];
}
