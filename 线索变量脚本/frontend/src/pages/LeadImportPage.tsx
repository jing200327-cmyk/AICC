import { useEffect, useState } from 'react';
import { FileUploadCard } from '../components/FileUploadCard';
import { ImportLogsPanel } from '../components/ImportLogsPanel';
import { ImportResultCard } from '../components/ImportResultCard';
import { ImportStatusCard } from '../components/ImportStatusCard';
import { StoreConfirmationDialog } from '../components/StoreConfirmationDialog';
import { Button } from '../components/ui/button';
import { useLeadImport } from '../hooks/useLeadImport';

export function LeadImportPage() {
  const { status, setStatus, jobDetail, error, uploadFile, downloadTxt, reset } = useLeadImport();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [confirmationOpen, setConfirmationOpen] = useState(false);

  useEffect(() => {
    setConfirmationOpen(status === 'need_confirmation');
  }, [status]);

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    if (status === 'idle') setStatus('file_selected');
  };

  const handleClear = () => {
    setSelectedFile(null);
    reset();
  };

  const handleSubmit = () => {
    if (selectedFile) void uploadFile(selectedFile);
  };

  const handleConfirmStore = (storeCode: string) => {
    setConfirmationOpen(false);
    if (selectedFile) void uploadFile(selectedFile, storeCode);
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-6 lg:px-8">
      <header className="mb-5 flex flex-col gap-3 border-b border-gray-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Lead Import</p>
          <h1 className="mt-1 text-2xl font-semibold text-gray-950">新增线索导入</h1>
          <p className="mt-2 text-sm text-gray-600">上传线索表后，后端识别门店、存入建银线索目录、执行白名单脚本并返回 txt 内容。</p>
        </div>
        {(status === 'completed' || status === 'failed') && (
          <Button type="button" variant="outline" onClick={handleClear}>继续上传新文件</Button>
        )}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="space-y-5">
          <FileUploadCard
            selectedFile={selectedFile}
            isUploading={status === 'uploading'}
            onFileSelect={handleFileSelect}
            onClear={handleClear}
            onSubmit={handleSubmit}
          />
          <ImportResultCard jobDetail={jobDetail} onDownload={downloadTxt} />
        </section>

        <aside className="space-y-5">
          <ImportStatusCard status={status} />
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="text-base font-semibold text-gray-950">处理规则</h2>
            <div className="mt-4 space-y-3 text-sm text-gray-600">
              <p>1. 根据文件名、sheet 名和表格内容识别门店。</p>
              <p>2. 上传文件保存到建银线索下的对应门店文件夹。</p>
              <p>3. 后端执行注册脚本并把 txt 内容展示在主界面。</p>
            </div>
          </section>
          <ImportLogsPanel logs={jobDetail?.logs || []} error={error || jobDetail?.error || null} />
        </aside>
      </div>

      <StoreConfirmationDialog
        isOpen={confirmationOpen}
        candidateStores={jobDetail?.candidate_stores || []}
        onClose={() => setConfirmationOpen(false)}
        onConfirm={handleConfirmStore}
      />
    </div>
  );
}
