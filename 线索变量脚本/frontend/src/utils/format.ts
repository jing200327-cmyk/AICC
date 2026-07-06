// 格式化文件大小
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// 格式化日期时间
export const formatDateTime = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

// 获取状态显示文本
export const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    idle: '等待上传',
    file_selected: '已选择文件',
    uploading: '上传中',
    pending: '待处理',
    processing: '处理中',
    need_confirmation: '需确认门店',
    completed: '处理完成',
    failed: '处理失败',
  };
  return statusMap[status] || status;
};

// 获取状态样式
export const getStatusVariant = (status: string): 'default' | 'success' | 'warning' | 'destructive' | 'secondary' => {
  switch (status) {
    case 'idle':
    case 'file_selected':
    case 'pending':
      return 'secondary';
    case 'processing':
    case 'uploading':
      return 'default';
    case 'completed':
      return 'success';
    case 'failed':
      return 'destructive';
    case 'need_confirmation':
      return 'warning';
    default:
      return 'secondary';
  }
};