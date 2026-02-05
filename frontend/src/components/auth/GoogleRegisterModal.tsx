// frontend/src/components/auth/GoogleRegisterModal.tsx
import { useState, FormEvent, useEffect } from 'react';
import API_BASE_URL from '../../config/api';

interface GoogleUserInfo {
    email: string;
    name: string;
    picture: string;
}

interface GoogleRegisterModalProps {
    isOpen: boolean;
    onClose: () => void;
    googleUser: GoogleUserInfo;
    onSuccess: () => void;
}

export default function GoogleRegisterModal({
    isOpen,
    onClose,
    googleUser,
    onSuccess
}: GoogleRegisterModalProps) {
    const [formData, setFormData] = useState({
        email: googleUser.email,
        full_name: '', // 不預設為 Gmail 名字
        identifier: '',
        department: '',
        role: 'student' as 'student' | 'teacher'
    });

    const [errors, setErrors] = useState<Record<string, string>>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState('');
    const [submitSuccess, setSubmitSuccess] = useState('');

    // 當 googleUser 改變時重置 email
    useEffect(() => {
        setFormData(prev => ({
            ...prev,
            email: googleUser.email,
            full_name: '' // 保持空白
        }));
    }, [googleUser.email]);

    if (!isOpen) return null;

    // 是否為教師
    const isTeacher = formData.role === 'teacher';

    // 驗證表單
    const validateForm = (): boolean => {
        const newErrors: Record<string, string> = {};

        // 學生需要填寫學號
        if (!isTeacher && !formData.identifier) {
            newErrors.identifier = '學號為必填欄位';
        }

        if (!formData.full_name) {
            newErrors.full_name = '姓名為必填欄位';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    // 處理表單提交
    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();

        if (!validateForm()) {
            return;
        }

        setIsSubmitting(true);
        setSubmitError('');
        setSubmitSuccess('');

        try {
            // 教師使用姓名作為 identifier
            const identifier = isTeacher ? formData.full_name : formData.identifier;

            const response = await fetch(`${API_BASE_URL}/api/auth/register-google`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: formData.email,
                    full_name: formData.full_name,
                    identifier: identifier,
                    department: formData.department,
                    role: formData.role
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || '註冊失敗');
            }

            // 註冊成功
            if (isTeacher) {
                // 教師需審核，顯示訊息
                setSubmitSuccess(result.message || '註冊成功，您的帳號需經管理員審核後方可使用。');
            } else {
                // 學生直接成功
                onSuccess();
            }
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : '註冊失敗，請稍後再試';
            setSubmitError(errorMessage);
        } finally {
            setIsSubmitting(false);
        }
    };

    // 處理輸入變化
    const handleChange = (field: string, value: string) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        if (errors[field]) {
            setErrors(prev => {
                const newErrors = { ...prev };
                delete newErrors[field];
                return newErrors;
            });
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <h2 className="text-2xl font-bold text-gray-800">完成註冊</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        aria-label="關閉"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    {/* Google 帳號資訊 */}
                    <div className="flex items-center gap-4 mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
                        {googleUser.picture && (
                            <img
                                src={googleUser.picture}
                                alt="Google Avatar"
                                className="w-12 h-12 rounded-full"
                            />
                        )}
                        <div>
                            <p className="font-medium text-gray-800">{googleUser.name}</p>
                            <p className="text-sm text-gray-500">{googleUser.email}</p>
                        </div>
                    </div>

                    <p className="text-sm text-gray-600 mb-6">
                        您的 Google 帳號尚未註冊，請填寫以下資訊完成註冊：
                    </p>

                    {/* 成功訊息 (教師審核) */}
                    {submitSuccess && (
                        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4">
                            <p className="font-medium">註冊成功！</p>
                            <p className="text-sm">{submitSuccess}</p>
                            <button
                                onClick={onClose}
                                className="mt-2 text-sm underline"
                            >
                                關閉視窗
                            </button>
                        </div>
                    )}

                    {!submitSuccess && (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* 身分選擇 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    身分 <span className="text-red-500">*</span>
                                </label>
                                <div className="flex gap-4">
                                    <label className="flex items-center cursor-pointer">
                                        <input
                                            type="radio"
                                            name="role"
                                            value="student"
                                            checked={formData.role === 'student'}
                                            onChange={(e) => handleChange('role', e.target.value)}
                                            className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                                            disabled={isSubmitting}
                                        />
                                        <span className="ml-2 text-gray-700">學生</span>
                                    </label>
                                    <label className="flex items-center cursor-pointer">
                                        <input
                                            type="radio"
                                            name="role"
                                            value="teacher"
                                            checked={formData.role === 'teacher'}
                                            onChange={(e) => handleChange('role', e.target.value)}
                                            className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                                            disabled={isSubmitting}
                                        />
                                        <span className="ml-2 text-gray-700">教師</span>
                                    </label>
                                </div>
                                {isTeacher && (
                                    <p className="text-xs text-amber-600 mt-1">
                                        ⚠️ 教師帳號需經管理員審核後方可使用
                                    </p>
                                )}
                            </div>

                            {/* 學號 (僅學生顯示) */}
                            {!isTeacher && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        學號 <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        value={formData.identifier}
                                        onChange={(e) => handleChange('identifier', e.target.value)}
                                        className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.identifier
                                            ? 'border-red-500 focus:ring-red-500'
                                            : 'border-gray-300 focus:ring-blue-500'
                                            }`}
                                        placeholder="例如：109123456"
                                        disabled={isSubmitting}
                                    />
                                    {errors.identifier && <p className="text-red-500 text-sm mt-1">{errors.identifier}</p>}
                                </div>
                            )}

                            {/* 姓名 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    姓名 <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={formData.full_name}
                                    onChange={(e) => handleChange('full_name', e.target.value)}
                                    className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.full_name
                                        ? 'border-red-500 focus:ring-red-500'
                                        : 'border-gray-300 focus:ring-blue-500'
                                        }`}
                                    placeholder="請輸入真實姓名"
                                    disabled={isSubmitting}
                                />
                                {errors.full_name && <p className="text-red-500 text-sm mt-1">{errors.full_name}</p>}
                            </div>

                            {/* 系所/單位 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    {isTeacher ? '服務單位' : '系所'}
                                </label>
                                <input
                                    type="text"
                                    value={formData.department}
                                    onChange={(e) => handleChange('department', e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder={isTeacher ? "例如：資訊工程學系" : "例如：資訊工程學系"}
                                    disabled={isSubmitting}
                                />
                            </div>

                            {/* Email (唯讀) */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Email
                                </label>
                                <input
                                    type="email"
                                    value={formData.email}
                                    readOnly
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-gray-500 cursor-not-allowed"
                                />
                                <p className="text-xs text-gray-400 mt-1">此 Email 與您的 Google 帳號關聯，無法修改</p>
                            </div>

                            {/* 錯誤訊息 */}
                            {submitError && (
                                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                                    {submitError}
                                </div>
                            )}

                            {/* 提交按鈕 */}
                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all ${isSubmitting
                                    ? 'bg-gray-400 cursor-not-allowed'
                                    : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:shadow-lg hover:-translate-y-0.5'
                                    }`}
                            >
                                {isSubmitting ? '註冊中...' : '完成註冊'}
                            </button>
                        </form>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
                    <p className="text-xs text-gray-500 text-center">
                        {isTeacher
                            ? '教師帳號審核通過後，將發送 Email 通知'
                            : '學生帳號註冊完成後將自動登入系統'}
                    </p>
                </div>
            </div>
        </div>
    );
}
