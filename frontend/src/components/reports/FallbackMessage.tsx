import React from 'react';

interface FallbackMessageProps {
  content?: string;
}

export const FallbackMessage: React.FC<FallbackMessageProps> = ({ content = "無法識別的內容或發生錯誤。" }) => {
  return (
    <div className="fallback-message p-4 bg-red-100 text-red-700 rounded-md">
      <p className="font-semibold">提示:</p>
      <p>{content}</p>
      <p className="text-sm mt-2">請檢查 API 返回的 display_type 或 content 格式。</p>
    </div>
  );
};
