import { useEffect } from 'react';
import { FaCheckCircle, FaTimes } from 'react-icons/fa';

interface ToastProps {
    message: string;
    type?: 'success' | 'error' | 'info';
    duration?: number;
    onClose: () => void;
}

function Toast({ message, type = 'success', duration = 3000, onClose }: ToastProps) {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    const bgColors = {
        success: 'bg-green-50 border-green-500',
        error: 'bg-red-50 border-red-500',
        info: 'bg-blue-50 border-blue-500'
    };

    const textColors = {
        success: 'text-green-800',
        error: 'text-red-800',
        info: 'text-blue-800'
    };

    const iconColors = {
        success: 'text-green-600',
        error: 'text-red-600',
        info: 'text-blue-600'
    };

    return (
        <div className="fixed top-20 right-6 z-50 animate-slide-in-right">
            <div className={`
                ${bgColors[type]} ${textColors[type]}
                px-6 py-4 rounded-lg shadow-lg border-l-4
                flex items-center gap-3 min-w-[320px] max-w-md
                transform transition-all duration-300
            `}>
                <FaCheckCircle className={`${iconColors[type]} flex-shrink-0`} size={20} />
                <p className="flex-1 font-medium">{message}</p>
                <button
                    onClick={onClose}
                    className={`${iconColors[type]} hover:opacity-70 transition-opacity`}
                >
                    <FaTimes size={16} />
                </button>
            </div>
        </div>
    );
}

export default Toast;
