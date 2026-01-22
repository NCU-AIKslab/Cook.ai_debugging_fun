import { useState, FormEvent, useEffect } from 'react';
import { DEPARTMENTS, SCHOOLS, type SchoolCode } from '../../constants/departments';
import API_BASE_URL from '../../config/api';

interface RegisterFormProps {
  onSuccess?: (message: string) => void;
  onError?: (error: string) => void;
}

interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  role?: string;
  student_id: string;
  major: string;
}

interface RegisterResponse {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
  message: string;
}

export default function RegisterForm({ onSuccess, onError }: RegisterFormProps) {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    student_id: '',
    school: '' as SchoolCode | '',
    major: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 驗證碼相關狀態
  const [verificationCode, setVerificationCode] = useState('');
  const [sentCode, setSentCode] = useState(false);
  const [isCodeVerified, setIsCodeVerified] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);

  // 倒數計時效果
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // 當學校改變時，清空科系選擇
  useEffect(() => {
    if (formData.school) {
      setFormData(prev => ({ ...prev, major: '' }));
    }
  }, [formData.school]);

  // 驗證 Email 格式
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // 驗證表單
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Email 驗證
    if (!formData.email) {
      newErrors.email = 'Email 為必填欄位';
    } else if (!validateEmail(formData.email)) {
      newErrors.email = '請輸入有效的 Email 格式';
    }

    // Email 驗證碼檢查
    if (!isCodeVerified) {
      newErrors.verificationCode = '請先驗證 Email';
    }

    // 密碼驗證
    if (!formData.password) {
      newErrors.password = '密碼為必填欄位';
    } else if (formData.password.length < 6) {
      newErrors.password = '密碼至少需要 6 個字元';
    }

    // 確認密碼驗證
    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = '密碼不一致';
    }

    // 姓名驗證
    if (!formData.full_name) {
      newErrors.full_name = '姓名為必填欄位';
    }

    // 學號驗證
    if (!formData.student_id) {
      newErrors.student_id = '學號為必填欄位';
    }

    // 學校驗證
    if (!formData.school) {
      newErrors.school = '請選擇學校';
    }

    // 科系驗證
    if (!formData.major) {
      newErrors.major = '請選擇科系';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 發送驗證碼
  const handleSendCode = async () => {
    // 驗證 Email 格式
    if (!formData.email) {
      setErrors(prev => ({ ...prev, email: 'Email 為必填欄位' }));
      return;
    }
    if (!validateEmail(formData.email)) {
      setErrors(prev => ({ ...prev, email: '請輸入有效的 Email 格式' }));
      return;
    }

    setIsSendingCode(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/send-verification-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: formData.email }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '發送驗證碼失敗');
      }

      setSentCode(true);
      setCountdown(60);
      setErrors(prev => ({ ...prev, email: '', verificationCode: '' }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '發送驗證碼失敗';
      setErrors(prev => ({ ...prev, email: errorMessage }));
    } finally {
      setIsSendingCode(false);
    }
  };

  // 驗證驗證碼
  const handleVerifyCode = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      setErrors(prev => ({ ...prev, verificationCode: '請輸入 6 位數驗證碼' }));
      return;
    }

    setIsVerifyingCode(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/verify-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: formData.email, code: verificationCode }),
      });

      const result = await response.json();

      if (result.verified) {
        setIsCodeVerified(true);
        setErrors(prev => ({ ...prev, verificationCode: '' }));
      } else {
        setErrors(prev => ({ ...prev, verificationCode: result.message || '驗證碼錯誤' }));
      }
    } catch (error) {
      setErrors(prev => ({ ...prev, verificationCode: '驗證失敗，請稍後再試' }));
    } finally {
      setIsVerifyingCode(false);
    }
  };

  // 處理表單提交
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      const registerData: RegisterData = {
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        student_id: formData.student_id,
        major: formData.major,
        role: 'student',
      };

      console.log('發送註冊請求:', registerData);

      // NOTE: Port is set to 8001 because 8000 is currently occupied.
      // If you are another developer using this registration function,
      // please manually change the port from 8001 back to 8000 if needed.
      // 直接呼叫 API
      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registerData),
      });

      console.log('收到回應:', response.status, response.statusText);

      if (!response.ok) {
        const error = await response.json();
        console.error('註冊失敗:', error);
        throw new Error(error.detail || '註冊失敗');
      }

      const result: RegisterResponse = await response.json();
      console.log('註冊成功:', result);

      if (onSuccess) {
        onSuccess(result.message || '註冊成功！');
      }

      // 清空表單
      setFormData({
        email: '',
        password: '',
        confirmPassword: '',
        full_name: '',
        student_id: '',
        school: '',
        major: '',
      });
      setVerificationCode('');
      setSentCode(false);
      setIsCodeVerified(false);
      setCountdown(0);
    } catch (error) {
      console.error('捕獲錯誤:', error);
      const errorMessage = error instanceof Error ? error.message : '註冊失敗，請稍後再試';
      if (onError) {
        onError(errorMessage);
      }
      setErrors({ submit: errorMessage });
    } finally {
      console.log('設定 isSubmitting = false');
      setIsSubmitting(false);
    }
  };

  // 處理輸入變化
  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // 清除該欄位的錯誤訊息
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }

    // 如果修改了 Email，重置驗證狀態
    if (field === 'email') {
      setSentCode(false);
      setIsCodeVerified(false);
      setVerificationCode('');
      setCountdown(0);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          Email <span className="text-red-500">*</span>
        </label>
        <div className="flex gap-2">
          <input
            type="email"
            id="email"
            value={formData.email}
            onChange={(e) => handleChange('email', e.target.value)}
            className={`flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.email
              ? 'border-red-500 focus:ring-red-500'
              : 'border-gray-300 focus:ring-blue-500'
              }`}
            placeholder="your.email@example.com"
            disabled={isSubmitting || isCodeVerified}
          />
          <button
            type="button"
            onClick={handleSendCode}
            disabled={isSubmitting || isSendingCode || countdown > 0 || isCodeVerified}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap ${isCodeVerified
              ? 'bg-green-500 text-white cursor-not-allowed'
              : countdown > 0
                ? 'bg-gray-400 text-white cursor-not-allowed'
                : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
          >
            {isCodeVerified ? '已驗證' : countdown > 0 ? `${countdown}秒` : isSendingCode ? '發送中...' : '發送驗證碼'}
          </button>
        </div>
        {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email}</p>}
      </div>

      {/* 驗證碼輸入 */}
      {sentCode && !isCodeVerified && (
        <div>
          <label htmlFor="verificationCode" className="block text-sm font-medium text-gray-700 mb-1">
            驗證碼 <span className="text-red-500">*</span>
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              id="verificationCode"
              value={verificationCode}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                setVerificationCode(value);
              }}
              className={`flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.verificationCode
                ? 'border-red-500 focus:ring-red-500'
                : 'border-gray-300 focus:ring-blue-500'
                }`}
              placeholder="請輸入 6 位數驗證碼"
              maxLength={6}
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={handleVerifyCode}
              disabled={isSubmitting || isVerifyingCode || verificationCode.length !== 6}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {isVerifyingCode ? '驗證中...' : '驗證'}
            </button>
          </div>
          {errors.verificationCode && <p className="text-red-500 text-sm mt-1">{errors.verificationCode}</p>}
        </div>
      )}

      {/* 密碼 */}
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
          密碼 <span className="text-red-500">*</span>
        </label>
        <input
          type="password"
          id="password"
          value={formData.password}
          onChange={(e) => handleChange('password', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.password
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          placeholder="至少 6 個字元"
          disabled={isSubmitting}
        />
        {errors.password && <p className="text-red-500 text-sm mt-1">{errors.password}</p>}
      </div>

      {/* 確認密碼 */}
      <div>
        <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
          確認密碼 <span className="text-red-500">*</span>
        </label>
        <input
          type="password"
          id="confirmPassword"
          value={formData.confirmPassword}
          onChange={(e) => handleChange('confirmPassword', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.confirmPassword
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          placeholder="再次輸入密碼"
          disabled={isSubmitting}
        />
        {errors.confirmPassword && (
          <p className="text-red-500 text-sm mt-1">{errors.confirmPassword}</p>
        )}
      </div>

      {/* 姓名 */}
      <div>
        <label htmlFor="full_name" className="block text-sm font-medium text-gray-700 mb-1">
          姓名 <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="full_name"
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

      {/* 學號 */}
      <div>
        <label htmlFor="student_id" className="block text-sm font-medium text-gray-700 mb-1">
          學號 <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="student_id"
          value={formData.student_id}
          onChange={(e) => handleChange('student_id', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.student_id
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          placeholder="例如：109123456"
          disabled={isSubmitting}
        />
        {errors.student_id && <p className="text-red-500 text-sm mt-1">{errors.student_id}</p>}
      </div>

      {/* 學校選擇 */}
      <div>
        <label htmlFor="school" className="block text-sm font-medium text-gray-700 mb-1">
          學校 <span className="text-red-500">*</span>
        </label>
        <select
          id="school"
          value={formData.school}
          onChange={(e) => handleChange('school', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.school
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          disabled={isSubmitting}
        >
          <option value="">請選擇學校</option>
          {SCHOOLS.map((school) => (
            <option key={school.code} value={school.code}>
              {school.name}
            </option>
          ))}
        </select>
        {errors.school && <p className="text-red-500 text-sm mt-1">{errors.school}</p>}
      </div>

      {/* 科系選擇 */}
      <div>
        <label htmlFor="major" className="block text-sm font-medium text-gray-700 mb-1">
          科系 <span className="text-red-500">*</span>
        </label>
        <select
          id="major"
          value={formData.major}
          onChange={(e) => handleChange('major', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.major
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          disabled={isSubmitting || !formData.school}
        >
          <option value="">請選擇科系</option>
          {formData.school && DEPARTMENTS[formData.school as SchoolCode]?.map((dept) => (
            <option key={dept} value={dept}>
              {dept}
            </option>
          ))}
        </select>
        {errors.major && <p className="text-red-500 text-sm mt-1">{errors.major}</p>}
        {!formData.school && <p className="text-gray-500 text-sm mt-1">請先選擇學校</p>}
      </div>

      {/* 錯誤訊息 */}
      {errors.submit && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {errors.submit}
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
        {isSubmitting ? '註冊中...' : '註冊'}
      </button>
    </form>
  );
}
