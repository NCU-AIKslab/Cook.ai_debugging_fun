// frontend/src/components/teacher/FileUpload.tsx

import React, { useState, useRef } from 'react';
import Fab from '@mui/material/Fab';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import Box from '@mui/material/Box';

interface FileUploadProps {
  onUploadSuccess: () => void; // Define the prop
}

function FileUpload({ onUploadSuccess }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!file) {
      setMessage('請先選擇一個檔案。');
      return;
    }

    setMessage(''); // Clear previous messages
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('http://localhost:8000/api/ingest', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      setMessage(`錯誤: ${data.detail || '上傳失敗'}`);
      // throw new Error(data.detail || '上傳失敗'); // No longer throwing to keep component state
      return;
    }

    setMessage(`成功! 檔案已攝取，ID: ${data.unique_content_id}`);
    onUploadSuccess();
    setFile(null); // Clear file after successful upload
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setFile(event.target.files[0]);
      setMessage('');
      // Automatically trigger upload after file selection
      // This will cause handleUpload to run with the newly set file
    }
  };

  // Effect to trigger upload when file state changes (after selection)
  React.useEffect(() => {
    if (file) {
      handleUpload();
    }
  }, [file]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }} // Hide the native input
      />
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
        <Fab
          color="primary"
          aria-label="上傳檔案"
          onClick={() => fileInputRef.current?.click()} // Trigger hidden input click
          size="medium"
          sx={{ boxShadow: 'none' }}
        >
          <UploadFileIcon />
        </Fab>
      </Box>
      {message && <p className="text-sm mt-2 text-center">{message}</p>}
      {file && <p className="text-sm mt-1 text-center text-neutral-text-secondary">已選取檔案: {file.name}</p>}
    </div>
  );
}

export default FileUpload;
