import React, { useState } from 'react';
import { FaEdit, FaUpload, FaLink, FaPlus } from 'react-icons/fa';
import FileUpload from './FileUpload';
import { Source } from './TeacherAICenter';
import Modal from '../common/Modal';
import Button from '../common/Button';

interface SourcePanelProps {
  availableSources: Source[];
  selectedSources: number[];
  onSelectSource: (uniqueContentId: number) => void;
  onUploadSuccess: () => void;
}

function SourcePanel({
  availableSources,
  selectedSources,
  onSelectSource,
  onUploadSuccess
}: SourcePanelProps) {

  const [editingId, setEditingId] = useState<string | null>(null);
  const [newName, setNewName] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'file' | 'link'>('file');

  const handleStartEditing = (source: Source) => {
    setEditingId(source.id);
    setNewName(source.name);
  };

  const handleCancelEditing = () => {
    setEditingId(null);
    setNewName('');
  };

  const handleRename = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!editingId || !newName.trim()) {
      handleCancelEditing();
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/materials/${editingId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: newName }),
      });

      if (!response.ok) {
        throw new Error('Failed to rename material');
      }

      onUploadSuccess();
      handleCancelEditing();
    } catch (error) {
      console.error("Error renaming material:", error);
      handleCancelEditing();
    }
  };

  const handleUploadAndClose = async () => {
    onUploadSuccess();
    await new Promise(resolve => setTimeout(resolve, 1500));
    setIsModalOpen(false);
  }

  return (
    <>
      <div className="h-full w-full bg-white rounded-xl border border-neutral-border flex flex-col relative shadow-card">
        <div className="h-full flex flex-col overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-neutral-border px-6">
            <h2 className="text-lg font-semibold text-neutral-text-main">
              參考資料
            </h2>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-4">
            <p className="text-neutral-text-tertiary text-sm mb-4">
              {availableSources.length} 個來源
            </p>

            <ul className="list-none p-0 m-0 space-y-1">
              {availableSources.map(source => (
                <li
                  key={source.id}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-theme-surface-hover transition-colors duration-200"
                >
                  <input
                    type="checkbox"
                    className="form-checkbox h-4 w-4 text-theme-checkbox border-neutral-border rounded focus:ring-theme-ring cursor-pointer"
                    checked={selectedSources.includes(source.unique_content_id)}
                    onChange={() => onSelectSource(source.unique_content_id)}
                  />
                  {editingId === source.id ? (
                    <form onSubmit={handleRename} className="flex-1">
                      <input
                        type="text"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onBlur={handleCancelEditing}
                        autoFocus
                        className="w-full px-2 py-1 text-sm border border-theme-primary rounded-lg focus:ring-2 focus:ring-theme-ring"
                      />
                    </form>
                  ) : (
                    <>
                      <span
                        className="truncate text-sm text-neutral-text-secondary flex-1 cursor-pointer hover:text-theme-primary transition-colors"
                        onClick={() => onSelectSource(source.unique_content_id)}
                      >
                        {source.name}
                      </span>
                      <button
                        onClick={() => handleStartEditing(source)}
                        className="text-neutral-icon hover:text-theme-primary transition-colors p-1"
                      >
                        <FaEdit className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Add button */}
        <button
          onClick={() => setIsModalOpen(true)}
          className="absolute bottom-6 right-6 w-12 h-12 rounded-full bg-theme-primary text-white flex items-center justify-center shadow-md hover:bg-theme-primary-hover hover:-translate-y-0.5 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-theme-ring focus:ring-offset-2"
          aria-label="新增來源"
        >
          <FaPlus className="w-5 h-5" />
        </button>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="新增來源"
      >
        <div>
          <div className="flex border-b border-neutral-border mb-4">
            <button
              onClick={() => setActiveTab('file')}
              className={`py-3 px-4 font-medium text-sm transition-colors ${activeTab === 'file'
                  ? 'border-b-2 border-theme-primary text-theme-primary'
                  : 'text-neutral-text-tertiary hover:text-neutral-text-secondary'
                }`}
            >
              <span className="flex items-center gap-2"><FaUpload /> 檔案上傳</span>
            </button>
            <button
              onClick={() => setActiveTab('link')}
              className={`py-3 px-4 font-medium text-sm transition-colors ${activeTab === 'link'
                  ? 'border-b-2 border-theme-primary text-theme-primary'
                  : 'text-neutral-text-tertiary hover:text-neutral-text-secondary'
                }`}
            >
              <span className="flex items-center gap-2"><FaLink /> 連結</span>
            </button>
          </div>

          <div>
            {activeTab === 'file' && (
              <FileUpload onUploadSuccess={handleUploadAndClose} />
            )}
            {activeTab === 'link' && (
              <div>
                <p className="text-sm text-neutral-text-tertiary mb-3">輸入網址來擷取內容。</p>
                <input
                  type="text"
                  placeholder="https://example.com"
                  className="w-full px-4 py-3 border border-neutral-border rounded-lg mb-3 focus:ring-2 focus:ring-theme-ring focus:border-theme-primary transition-colors"
                />
                <Button
                  variant="secondary"
                  className="w-full"
                  idleText="讀取連結內容"
                />
              </div>
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}

export default SourcePanel;