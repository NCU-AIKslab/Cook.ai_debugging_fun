import { useState, FormEvent } from 'react';
import API_BASE_URL from '../../config/api';

interface RegisterFormProps {
  onSuccess?: (message: string) => void;
  onError?: (error: string) => void;
}

interface RegisterData {
  stu_id: string;
  stu_name: string;
  stu_pwd: string;
  role: 'student' | 'teacher';
}

interface RegisterResponse {
  stu_id: string;
  stu_name: string;
  is_teacher: boolean;
  message: string;
}

export default function RegisterForm({ onSuccess, onError }: RegisterFormProps) {
  const [formData, setFormData] = useState({
    stu_id: '',
    stu_name: '',
    stu_pwd: '',
    confirmPassword: '',
    role: 'student' as 'student' | 'teacher',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isTeacher = formData.role === 'teacher';

  // 驗證表單
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // 學生必填學號
    if (!isTeacher && !formData.stu_id) {
      newErrors.stu_id = '學號為必填欄位';
    }

    if (!formData.stu_name) {
      newErrors.stu_name = '姓名為必填欄位';
    }

    if (!formData.stu_pwd) {
      newErrors.stu_pwd = '密碼為必填欄位';
    }

    if (formData.stu_pwd !== formData.confirmPassword) {
      newErrors.confirmPassword = '密碼不一致';
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

    try {
      const registerData: RegisterData = {
        // 教師自動使用姓名作為 ID
        stu_id: isTeacher ? formData.stu_name : formData.stu_id,
        stu_name: formData.stu_name,
        stu_pwd: formData.stu_pwd,
        role: formData.role,
      };

      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registerData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '註冊失敗');
      }

      const result: RegisterResponse = await response.json();

      if (onSuccess) {
        onSuccess(result.message || '註冊成功！');
      }

      // 清空表單
      setFormData({
        stu_id: '',
        stu_name: '',
        stu_pwd: '',
        confirmPassword: '',
        role: 'student',
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '註冊失敗，請稍後再試';
      if (onError) {
        onError(errorMessage);
      }
      setErrors({ submit: errorMessage });
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
            ⚠️ 教師身分需等待後臺確認才能使用
          </p>
        )}
      </div>

      {/* 學號 (僅學生顯示) */}
      {!isTeacher && (
        <div>
          <label htmlFor="stu_id" className="block text-sm font-medium text-gray-700 mb-1">
            學號 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="stu_id"
            value={formData.stu_id}
            onChange={(e) => handleChange('stu_id', e.target.value)}
            className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.stu_id
              ? 'border-red-500 focus:ring-red-500'
              : 'border-gray-300 focus:ring-blue-500'
              }`}
            placeholder="例如：109123456"
            disabled={isSubmitting}
          />
          {errors.stu_id && <p className="text-red-500 text-sm mt-1">{errors.stu_id}</p>}
        </div>
      )}

      {/* 姓名 */}
      <div>
        <label htmlFor="stu_name" className="block text-sm font-medium text-gray-700 mb-1">
          姓名 <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="stu_name"
          value={formData.stu_name}
          onChange={(e) => handleChange('stu_name', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.stu_name
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          placeholder="請輸入真實姓名"
          disabled={isSubmitting}
        />
        {errors.stu_name && <p className="text-red-500 text-sm mt-1">{errors.stu_name}</p>}
      </div>

      {/* 密碼 */}
      <div>
        <label htmlFor="stu_pwd" className="block text-sm font-medium text-gray-700 mb-1">
          密碼 <span className="text-red-500">*</span>
        </label>
        <input
          type="password"
          id="stu_pwd"
          value={formData.stu_pwd}
          onChange={(e) => handleChange('stu_pwd', e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 ${errors.stu_pwd
            ? 'border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:ring-blue-500'
            }`}
          placeholder="請輸入密碼"
          disabled={isSubmitting}
        />
        {errors.stu_pwd && <p className="text-red-500 text-sm mt-1">{errors.stu_pwd}</p>}
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
