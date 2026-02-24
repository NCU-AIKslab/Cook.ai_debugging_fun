// frontend/src/components/auth/RegisterModal.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useUser } from '../../contexts/UserContext';
import API_BASE_URL from '../../config/api';
import RegisterForm from './RegisterForm';

interface RegisterModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface GoogleUserInfo {
  email: string;
  name: string;
  picture: string;
}


export default function RegisterModal({ isOpen, onClose }: RegisterModalProps) {
  const navigate = useNavigate();
  const { setUser } = useUser();
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);




  // 註冊表單狀態
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [googleUserInfo, setGoogleUserInfo] = useState<GoogleUserInfo | null>(null);
  const [pendingGoogleToken, setPendingGoogleToken] = useState<string | null>(null);

  // 註冊表單資料
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',  // 姓名預設空白
    identifier: '',
    department: '',
    role: 'student' as 'student' | 'teacher'
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // 追蹤一般表單裡選的身分（用於標題顯示）
  const [localRole, setLocalRole] = useState<'student' | 'teacher'>('student');

  if (!isOpen) return null;

  // 是否為教師
  const isTeacher = formData.role === 'teacher';

  const handleClose = () => {
    setSuccessMessage('');
    setErrorMessage('');
    setShowRegisterForm(false);
    setGoogleUserInfo(null);
    setPendingGoogleToken(null);
    setLocalRole('student');
    setFormData({
      email: '',
      full_name: '',
      identifier: '',
      department: '',
      role: 'student'
    });
    setFormErrors({});
    onClose();
  };


  // 處理表單輸入變化
  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (formErrors[field]) {
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  // 驗證註冊表單
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.email) {
      newErrors.email = 'Email 為必填欄位';
    }

    if (!formData.full_name) {
      newErrors.full_name = '姓名為必填欄位';
    }

    // 學生需要填寫學號，教師不需要（用姓名作為 identifier）
    if (!isTeacher && !formData.identifier) {
      newErrors.identifier = '學號為必填欄位';
    }

    setFormErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 提交註冊表單
  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    setErrorMessage('');

    try {
      // 教師使用姓名作為 identifier
      const identifier = isTeacher ? formData.full_name : formData.identifier;

      // 1. 呼叫 register-google API (Central Auth register-direct)
      const registerResponse = await fetch(`${API_BASE_URL}/api/auth/register-google`, {
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

      const result = await registerResponse.json();

      if (!registerResponse.ok) {
        throw new Error(result.detail || '註冊失敗');
      }

      // 2. 教師需審核
      if (isTeacher) {
        setSuccessMessage(result.message || '註冊成功！您的帳號需經管理員審核後方可使用。');
        setShowRegisterForm(false);
        setIsLoading(false);
        return;
      }

      // 3. 學生註冊成功後，嘗試再次 Google 登入
      if (pendingGoogleToken) {
        const loginResponse = await fetch(`${API_BASE_URL}/api/auth/google`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: pendingGoogleToken })
        });

        if (!loginResponse.ok) {
          // 如果登入失敗，顯示成功訊息並請使用者重新登入
          setSuccessMessage('註冊成功！請重新點擊 Google 登入。');
          setShowRegisterForm(false);
          setIsLoading(false);
          return;
        }

        const data = await loginResponse.json();

        const userData = {
          user_id: data.user_id,
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
      } else {
        setSuccessMessage('註冊成功！請使用 Google 登入。');
        setShowRegisterForm(false);
      }
    } catch (err: any) {
      setErrorMessage(err.message || '註冊失敗，請稍後再試');
    } finally {
      setIsLoading(false);
    }
  };

  // 一般註冊成功
  const handleLocalRegisterSuccess = (message: string) => {
    setSuccessMessage(message);
    setLocalRole('student');
  };

  // 一般註冊失敗
  const handleLocalRegisterError = (error: string) => {
    setErrorMessage(error);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-800">
            {showRegisterForm
              ? (formData.role === 'teacher' ? '教師 Google 註冊' : '學生 Google 註冊')
              : (localRole === 'teacher' ? '教師註冊' : '學生註冊')}
          </h2>
          <button
            onClick={handleClose}
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
          {/* 成功訊息 */}
          {successMessage && (
            <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>{successMessage}</span>
              </div>
              <button
                onClick={handleClose}
                className="mt-2 text-sm underline"
              >
                關閉
              </button>
            </div>
          )}

          {/* 錯誤訊息 */}
          {errorMessage && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}

          {/* 顯示 Google 註冊表單 */}
          {showRegisterForm && googleUserInfo ? (
            <>
              {/* Google 帳號資訊 */}
              <div className="flex items-center gap-4 mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
                {googleUserInfo.picture && (
                  <img
                    src={googleUserInfo.picture}
                    alt="Google Avatar"
                    className="w-12 h-12 rounded-full"
                  />
                )}
                <div>
                  <p className="font-medium text-gray-800">{googleUserInfo.name}</p>
                  <p className="text-sm text-gray-500">{googleUserInfo.email}</p>
                </div>
              </div>

              <p className="text-sm text-gray-600 mb-6">
                您的 Google 帳號尚未註冊，請填寫以下資訊完成註冊：
              </p>

              <form onSubmit={handleRegisterSubmit} className="space-y-4">
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
                        disabled={isLoading}
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
                        disabled={isLoading}
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
                      className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${formErrors.identifier
                        ? 'border-red-500 focus:ring-red-500'
                        : 'border-gray-300 focus:ring-blue-500'
                        }`}
                      placeholder="例如：109123456"
                      disabled={isLoading}
                    />
                    {formErrors.identifier && <p className="text-red-500 text-sm mt-1">{formErrors.identifier}</p>}
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
                    className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${formErrors.full_name
                      ? 'border-red-500 focus:ring-red-500'
                      : 'border-gray-300 focus:ring-blue-500'
                      }`}
                    placeholder="請輸入真實姓名"
                    disabled={isLoading}
                  />
                  {formErrors.full_name && <p className="text-red-500 text-sm mt-1">{formErrors.full_name}</p>}
                </div>

                {/* 系級/服務單位 */}
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
                    disabled={isLoading}
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

                {/* 提交按鈕 */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all ${isLoading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:shadow-lg hover:-translate-y-0.5'
                    }`}
                >
                  {isLoading ? '註冊中...' : '完成註冊'}
                </button>
              </form>
            </>
          ) : (
            <RegisterForm
              onSuccess={handleLocalRegisterSuccess}
              onError={handleLocalRegisterError}
              onRoleChange={(role) => setLocalRole(role)}
            />
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-lg">
          <p className="text-sm text-gray-600 text-center">
            已經有帳號？{' '}
            <button
              onClick={handleClose}
              className="text-blue-600 hover:text-blue-800 font-medium"
            >
              立即登入
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
