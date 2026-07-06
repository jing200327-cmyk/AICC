import { FileText, Loader2, Upload, X } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { formatFileSize } from '@/utils/format';
import { Button } from './ui/button';

interface FileUploadCardProps {
  selectedFile: File | null;
  isUploading: boolean;
  onFileSelect: (file: File) => void;
  onClear: () => void;
  onSubmit: () => void;
}

const SUPPORTED_EXTENSIONS = ['xlsx', 'xls', 'csv'];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

export function FileUploadCard({ selectedFile, isUploading, onFileSelect, onClear, onSubmit }: FileUploadCardProps) {
  const [error, setError] = useState('');

  const validateAndSelect = useCallback((file: File) => {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!extension || !SUPPORTED_EXTENSIONS.includes(extension)) {
      setError('仅支持 xlsx、xls、csv 格式文件');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('文件不能超过 20MB');
      return;
    }
    setError('');
    onFileSelect(file);
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    multiple: false,
    disabled: isUploading,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
    },
    onDrop: (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (file) validateAndSelect(file);
    },
  });

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-gray-950">上传线索数据表</h2>
          <p className="mt-1 text-sm text-gray-500">系统会根据文件名和表格内容识别门店，保存到对应门店文件夹并生成 txt。</p>
        </div>
        <span className="rounded border border-gray-200 px-2 py-1 text-xs text-gray-500">xlsx / xls / csv</span>
      </div>

      {!selectedFile ? (
        <div
          {...getRootProps()}
          className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 px-6 py-10 text-center outline-none transition hover:border-gray-500 hover:bg-white focus-visible:ring-2 focus-visible:ring-gray-900"
        >
          <input {...getInputProps()} aria-label="选择线索数据表" />
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-md bg-gray-900 text-white">
            <Upload className="h-7 w-7" />
          </div>
          <p className="text-sm font-semibold text-gray-950">
            {isDragActive ? '松开后读取文件' : '点击选择文件，或拖拽到此处'}
          </p>
          <p className="mt-2 max-w-md text-sm text-gray-500">上传后后端会自动识别门店，不允许前端传任意脚本路径或输出目录。</p>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-11 w-11 flex-none items-center justify-center rounded-md bg-white text-gray-600 ring-1 ring-gray-200">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-gray-950">{selectedFile.name}</p>
                <p className="mt-1 text-xs text-gray-500">{formatFileSize(selectedFile.size)}</p>
              </div>
            </div>
            <Button type="button" variant="ghost" size="icon" onClick={onClear} disabled={isUploading} aria-label="移除文件">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button type="button" size="lg" className="w-full sm:w-auto" onClick={onSubmit} disabled={!selectedFile || isUploading}>
          {isUploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
          {isUploading ? '正在导入' : '开始导入并生成 txt'}
        </Button>
        <p className="text-xs text-gray-500">默认输出在建银线索下的识别门店文件夹。</p>
      </div>
    </section>
  );
}
