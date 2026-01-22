// frontend/src/components/common/Modal.tsx
import React from 'react';
import ReactDOM from 'react-dom';
import { FaTimes } from 'react-icons/fa';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title?: string;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, title }) => {
  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <>
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
        onClick={onClose}
      ></div>

      {/* Modal Content */}
      <div 
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl z-50 w-full max-w-lg mx-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-theme-border">
          <h3 className="text-lg font-bold text-neutral-text-main">{title || ''}</h3>
          <button 
            onClick={onClose}
            className="p-1 rounded-full text-neutral-icon hover:bg-neutral-background"
          >
            <FaTimes className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {children}
        </div>
      </div>
    </>,
    document.body // Render modal in the body to avoid z-index issues
  );
};

export default Modal;
