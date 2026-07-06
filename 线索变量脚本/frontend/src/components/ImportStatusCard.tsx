import { CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react';
import type { ImportStatus } from '../types/leadImport';

interface ImportStatusCardProps {
  status: ImportStatus;
}

const statusText: Record<ImportStatus, string> = {
  idle: '等待上传',
  file_selected: '已选择文件',
  uploading: '正在上传',
  pending: '等待处理',
  processing: '正在处理',
  need_confirmation: '需要确认门店',
  completed: '处理完成',
  failed: '处理失败',
};

export function ImportStatusCard({ status }: ImportStatusCardProps) {
  const Icon = status === 'completed' ? CheckCircle2 : status === 'failed' ? XCircle : status === 'uploading' || status === 'processing' ? Loader2 : Clock;
  const tone = status === 'completed' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : status === 'failed' ? 'text-red-700 bg-red-50 border-red-200' : 'text-gray-700 bg-gray-50 border-gray-200';

  return (
    <section className={`rounded-lg border p-4 ${tone}`}>
      <div className="flex items-center gap-3">
        <Icon className={`h-5 w-5 ${Icon === Loader2 ? 'animate-spin' : ''}`} />
        <div>
          <h2 className="text-sm font-semibold">处理状态</h2>
          <p className="mt-1 text-sm">{statusText[status]}</p>
        </div>
      </div>
    </section>
  );
}
