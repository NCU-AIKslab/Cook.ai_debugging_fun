// frontend/src/components/auth/LoginModal.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import Button from '../common/Button';
import API_BASE_URL from '../../config/api';

interface LoginModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function LoginModal({ isOpen, onClose }: LoginModalProps) {
    const navigate = useNavigate();
    const { setUser } = useUser();
    const [form, setForm] = useState({ stu_id: '', stu_pwd: '' });
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form)
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || '登入失敗');
            }

            const data = await response.json();

            // 儲存使用者資訊
            const userData = {
                user_id: data.stu_id,
                full_name: data.stu_name,
                role: 'student'
            };

            localStorage.setItem('user', JSON.stringify(userData));
            setUser(userData);

            // 關閉 Modal
            onClose();

            // 導向學生頁面
            navigate('/student');
        } catch (err: any) {
            setError(err.message || '登入失敗，請檢查您的學號密碼');
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setForm({ stu_id: '', stu_pwd: '' });
        setError('');
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <h2 className="text-2xl font-bold text-gray-800">登入</h2>
                    <button
                        onClick={handleClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        aria-label="關閉"
                    >
                        <svg
                            className="w-6 h-6"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    {error && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center">
                            <svg
                                className="w-5 h-5 mr-2"
                                fill="currentColor"
                                viewBox="0 0 20 20"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                    clipRule="evenodd"
                                />
                            </svg>
                            <span>{error}</span>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                學號
                            </label>
                            <input
                                type="text"
                                required
                                value={form.stu_id}
                                onChange={(e) => setForm({ ...form, stu_id: e.target.value })}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                placeholder="請輸入學號"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                密碼
                            </label>
                            <input
                                type="password"
                                required
                                value={form.stu_pwd}
                                onChange={(e) => setForm({ ...form, stu_pwd: e.target.value })}
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                placeholder="請輸入密碼"
                            />
                        </div>

                        <Button
                            type="submit"
                            disabled={isLoading}
                            className="w-full"
                            idleText={isLoading ? '登入中...' : '登入'}
                        />
                    </form>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-lg">
                    <p className="text-sm text-gray-600 text-center">
                        還沒有帳號？{' '}
                        <button
                            onClick={handleClose}
                            className="text-blue-600 hover:text-blue-800 font-medium"
                        >
                            立即註冊
                        </button>
                    </p>
                </div>
            </div>
        </div>
    );
}
