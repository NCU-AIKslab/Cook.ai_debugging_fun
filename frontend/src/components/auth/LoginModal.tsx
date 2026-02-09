// frontend/src/components/auth/LoginModal.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useUser } from '../../contexts/UserContext';
import Button from '../common/Button';
import API_BASE_URL from '../../config/api';
import GoogleRegisterModal from './GoogleRegisterModal';

interface LoginModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface GoogleUserInfo {
    email: string;
    name: string;
    picture: string;
}

export default function LoginModal({ isOpen, onClose }: LoginModalProps) {
    const navigate = useNavigate();
    const { setUser } = useUser();
    const [form, setForm] = useState({ stu_id: '', stu_pwd: '' });
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // Google 註冊 Modal 狀態
    const [showGoogleRegister, setShowGoogleRegister] = useState(false);
    const [googleUserInfo, setGoogleUserInfo] = useState<GoogleUserInfo | null>(null);
    const [pendingGoogleToken, setPendingGoogleToken] = useState<string | null>(null);

    if (!isOpen && !showGoogleRegister) return null;

    // 手動登入
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

            console.log('[LoginDebug] Raw keys:', Object.keys(data));
            console.log('[LoginDebug] is_teacher val:', data.is_teacher, 'type:', typeof data.is_teacher);

            const isTeacherBool = Boolean(data.is_teacher);
            const roleStr = isTeacherBool ? 'teacher' : 'student';

            console.log('[LoginDebug] Resolved Role:', roleStr);

            // 儲存使用者資訊
            // Align with Google Login structure (role, identifier)
            const userData = {
                user_id: data.stu_id,
                full_name: data.stu_name,
                role: roleStr,
                identifier: data.stu_id, // Use stu_id as identifier for local users
                email: "" // Local users may not have email populated in response yet
            };

            console.log('[LoginDebug] API Response:', data);
            console.log('[LoginDebug] UserData to save:', userData);

            localStorage.setItem('user', JSON.stringify(userData));
            setUser(userData);

            // 關閉 Modal
            onClose();

            // 根據角色導向不同頁面
            navigate(data.is_teacher ? '/teacher' : '/student');
        } catch (err: any) {
            setError(err.message || '登入失敗，請檢查您的學號密碼');
        } finally {
            setIsLoading(false);
        }
    };

    // Google 登入成功
    const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
        setError('');
        setIsLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: credentialResponse.credential })
            });

            const data = await response.json();

            // 處理 404 USER_NOT_FOUND - 需要先註冊
            if (response.status === 404 && data.code === 'USER_NOT_FOUND') {
                // 保存 Google 使用者資訊並開啟註冊 Modal
                setGoogleUserInfo({
                    email: data.google_user?.email || '',
                    name: data.google_user?.name || '',
                    picture: data.google_user?.picture || ''
                });
                setPendingGoogleToken(credentialResponse.credential || null);
                setShowGoogleRegister(true);
                setIsLoading(false);
                return;
            }

            if (!response.ok) {
                throw new Error(data.detail || 'Google 登入失敗');
            }

            // 登入成功
            const userData = {
                user_id: data.identifier, // Use identifier (student ID/name) as user_id
                full_name: data.full_name,
                role: data.is_teacher ? 'teacher' : 'student',
                access_token: data.access_token,
                email: data.email,
                identifier: data.identifier,
                department: data.department
            };

            localStorage.setItem('user', JSON.stringify(userData));
            setUser(userData);

            // 關閉 Modal
            onClose();

            // 根據角色導向不同頁面
            navigate(data.is_teacher ? '/teacher' : '/student');
        } catch (err: any) {
            setError(err.message || 'Google 登入失敗');
        } finally {
            setIsLoading(false);
        }
    };

    // Google 登入失敗
    const handleGoogleError = () => {
        setError('Google 登入失敗，請稍後再試');
    };

    const handleClose = () => {
        setForm({ stu_id: '', stu_pwd: '' });
        setError('');
        onClose();
    };

    // 註冊成功後自動登入
    const handleRegisterSuccess = async () => {
        setShowGoogleRegister(false);

        // 註冊成功後，嘗試再次 Google 登入
        if (pendingGoogleToken) {
            setIsLoading(true);
            try {
                const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: pendingGoogleToken })
                });

                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.detail || '登入失敗');
                }

                const data = await response.json();

                const userData = {
                    user_id: data.identifier, // Use identifier (student ID/name) as user_id
                    full_name: data.full_name,
                    role: data.is_teacher ? 'teacher' : 'student',
                    access_token: data.access_token,
                    email: data.email,
                    identifier: data.identifier,
                    department: data.department
                };

                localStorage.setItem('user', JSON.stringify(userData));
                setUser(userData);
                onClose();
                navigate(data.is_teacher ? '/teacher' : '/student');
            } catch (err: any) {
                setError(err.message || '登入失敗，請重新點擊 Google 登入');
            } finally {
                setIsLoading(false);
                setPendingGoogleToken(null);
            }
        }
    };

    // 渲染 Google 註冊 Modal
    if (showGoogleRegister && googleUserInfo) {
        return (
            <GoogleRegisterModal
                isOpen={showGoogleRegister}
                onClose={() => {
                    setShowGoogleRegister(false);
                    setGoogleUserInfo(null);
                    setPendingGoogleToken(null);
                }}
                googleUser={googleUserInfo}
                onSuccess={handleRegisterSuccess}
            />
        );
    }

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

                    <div className="mt-4 mb-2 text-center">
                        <p className="text-sm text-gray-600">
                            還沒有帳號？{' '}
                            <button
                                onClick={handleClose}
                                className="text-blue-600 hover:text-blue-800 font-medium"
                            >
                                立即註冊
                            </button>
                        </p>
                    </div>

                    {/* 分隔線 */}
                    <div className="flex items-center gap-4 my-6">
                        <div className="h-px bg-gray-300 flex-1"></div>
                        <span className="text-gray-500 text-sm">or</span>
                        <div className="h-px bg-gray-300 flex-1"></div>
                    </div>

                    {/* Google 登入按鈕 */}
                    <div className="mb-6">
                        <div className="flex justify-center">
                            <GoogleLogin
                                onSuccess={handleGoogleSuccess}
                                onError={handleGoogleError}
                                text="continue_with"
                                shape="rectangular"
                                size="large"
                                width="320"
                            />
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-lg">
                </div>
            </div>
        </div>
    );
}
