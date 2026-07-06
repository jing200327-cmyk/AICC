import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FileUploadCard } from '../FileUploadCard';
import { ImportLogsPanel } from '../ImportLogsPanel';
import { ImportResultCard } from '../ImportResultCard';
import { ImportStatusCard } from '../ImportStatusCard';
import { StoreConfirmationDialog } from '../StoreConfirmationDialog';
import type { JobDetailResponse } from '../../types/leadImport';

afterEach(() => cleanup());

describe('lead import UI', () => {
  it('renders upload action disabled before file selection', () => {
    render(<FileUploadCard selectedFile={null} isUploading={false} onFileSelect={vi.fn()} onClear={vi.fn()} onSubmit={vi.fn()} />);

    expect(screen.getByRole('button', { name: '开始导入并生成 txt' })).toBeDisabled();
  });

  it('shows selected file information and enables upload', async () => {
    const file = new File(['plate,model'], '武汉银马-测试.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const user = userEvent.setup();

    render(<FileUploadCard selectedFile={file} isUploading={false} onFileSelect={vi.fn()} onClear={vi.fn()} onSubmit={vi.fn()} />);

    expect(screen.getByText('武汉银马-测试.xlsx')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始导入并生成 txt' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '移除文件' }));
  });

  it('renders processing status', () => {
    render(<ImportStatusCard status="processing" />);

    expect(screen.getByText('正在处理')).toBeInTheDocument();
  });

  it('renders completed result with store, output content and download button', () => {
    const job: JobDetailResponse = {
      job_id: 'job_test_001',
      status: 'completed',
      detected_store: { store_code: 'wuhan_yinma', store_name: '武汉银马店', confidence: 0.95, matched_by: ['filename'] },
      candidate_stores: [],
      input_file: { filename: '武汉银马-测试.xlsx', size: 128, saved_path: 'E:/ai/workflow/线索变量脚本/建银线索/武汉银马/job_test_001_武汉银马-测试.xlsx' },
      output: {
        txt_file_path: 'E:/ai/workflow/线索变量脚本/建银线索/武汉银马/job_test_001.txt',
        download_url: '/api/leads/import/jobs/job_test_001/download',
        txt_preview: '{"carNo":"鄂.A12345"}',
      },
      logs: ['TXT generated'],
      error: null,
      created_at: '2026-07-03T10:00:00+08:00',
      updated_at: '2026-07-03T10:00:01+08:00',
    };

    render(<ImportResultCard jobDetail={job} onDownload={vi.fn()} />);

    expect(screen.getByText('武汉银马店')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下载 txt' })).toBeEnabled();
    expect(screen.getByText(/鄂.A12345/)).toBeInTheDocument();
  });

  it('renders failed error message', () => {
    render(<ImportLogsPanel logs={[]} error={{ code: 'UPLOAD_ERROR', message: '文件上传失败' }} />);

    expect(screen.getByRole('alert')).toHaveTextContent('文件上传失败');
  });

  it('renders candidate stores for confirmation', () => {
    render(
      <StoreConfirmationDialog
        isOpen={true}
        candidateStores={[{ store_code: 'wuhan_yinma', store_name: '武汉银马店', confidence: 0.82 }]}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText('需要人工确认门店')).toBeInTheDocument();
    expect(screen.getByText('武汉银马店')).toBeInTheDocument();
  });
});
