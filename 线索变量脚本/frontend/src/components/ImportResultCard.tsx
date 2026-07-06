import { Download, FileText, Store } from 'lucide-react';
import type { JobDetailResponse } from '../types/leadImport';
import { Button } from './ui/button';

interface ImportResultCardProps {
  jobDetail: JobDetailResponse | null;
  onDownload: () => void;
}

export function ImportResultCard({ jobDetail, onDownload }: ImportResultCardProps) {
  if (!jobDetail) {
    return (
      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 text-base font-semibold text-gray-950">
          <Store className="h-5 w-5" />
          识别与输出
        </div>
        <p className="mt-3 text-sm text-gray-500">上传后这里会显示门店识别、保存路径和 txt 文本内容。</p>
      </section>
    );
  }

  const store = jobDetail.detected_store;
  const txtContent = jobDetail.output?.txt_preview || '';

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-base font-semibold text-gray-950">
          <Store className="h-5 w-5" />
          识别与输出
        </div>
        <Button type="button" variant="outline" onClick={onDownload} disabled={jobDetail.status !== 'completed'}>
          <Download className="mr-2 h-4 w-4" />
          下载 txt
        </Button>
      </div>

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-md bg-gray-50 p-3">
          <dt className="text-xs text-gray-500">任务状态</dt>
          <dd className="mt-1 font-medium text-gray-950">{jobDetail.status}</dd>
        </div>
        <div className="rounded-md bg-gray-50 p-3">
          <dt className="text-xs text-gray-500">识别门店</dt>
          <dd className="mt-1 font-medium text-gray-950">{store?.store_name || '-'}</dd>
        </div>
        <div className="rounded-md bg-gray-50 p-3">
          <dt className="text-xs text-gray-500">门店编码</dt>
          <dd className="mt-1 font-medium text-gray-950">{store?.store_code || '-'}</dd>
        </div>
        <div className="rounded-md bg-gray-50 p-3">
          <dt className="text-xs text-gray-500">置信度</dt>
          <dd className="mt-1 font-medium text-gray-950">{store ? `${Math.round(store.confidence * 100)}%` : '-'}</dd>
        </div>
      </dl>

      <div className="mt-4 grid gap-3 text-sm">
        <div>
          <p className="mb-1 text-xs text-gray-500">原表保存路径</p>
          <p className="break-all rounded-md bg-gray-50 p-3 text-gray-800">{jobDetail.input_file.saved_path || '-'}</p>
        </div>
        <div>
          <p className="mb-1 text-xs text-gray-500">txt 文件路径</p>
          <p className="break-all rounded-md bg-gray-50 p-3 text-gray-800">{jobDetail.output?.txt_file_path || '-'}</p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-950">
          <FileText className="h-4 w-4" />
          txt 文本内容
        </div>
        <pre className="min-h-40 max-h-96 overflow-auto rounded-md border border-gray-200 bg-gray-950 p-4 text-xs leading-5 text-gray-50">
          {txtContent || '处理完成后显示生成的 txt 内容。'}
        </pre>
      </div>
    </section>
  );
}
