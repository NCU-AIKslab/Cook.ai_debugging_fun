import { useState } from 'react';
import RegisterForm from './RegisterForm';
import { SCHOOLS, type SchoolCode } from '../../constants/departments';
import API_BASE_URL from '../../config/api';

interface RegisterModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function RegisterModal({ isOpen, onClose }: RegisterModalProps) {
  const [activeTab, setActiveTab] = useState<'student' | 'teacher'>('student');
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // 教師表單狀態
  const [teacherForm, setTeacherForm] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    school: '' as SchoolCode | '',
  });
  const [proofDocument, setProofDocument] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSuccess = (message: string) => {
    setSuccessMessage(message);
    setErrorMessage('');

    // 3 秒後自動關閉 Modal
    setTimeout(() => {
      setSuccessMessage('');
      onClose();
    }, 3000);
  };

  const handleError = (error: string) => {
    setErrorMessage(error);
    setSuccessMessage('');
  };

  const handleClose = () => {
    setSuccessMessage('');
    setErrorMessage('');
    setActiveTab('student');
    setTeacherForm({
      email: '',
      password: '',
      confirmPassword: '',
      full_name: '',
      school: '',
    });
    setProofDocument(null);
    onClose();
  };

  const handleTeacherSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 驗證表單
    if (!teacherForm.email || !teacherForm.password || !teacherForm.full_name || !teacherForm.school) {
      handleError('請填寫所有必填欄位');
      return;
    }

    if (teacherForm.password !== teacherForm.confirmPassword) {
      handleError('密碼不一致');
      return;
    }

    if (teacherForm.password.length < 6) {
      handleError('密碼至少需要 6 個字元');
      return;
    }

    setIsSubmitting(true);

    try {
      // 從 school code 找出學校名稱
      const selectedSchool = SCHOOLS.find(s => s.code === teacherForm.school);
      const institution = selectedSchool?.name || teacherForm.school;

      const formData = new FormData();
      formData.append('email', teacherForm.email);
      formData.append('password', teacherForm.password);
      formData.append('full_name', teacherForm.full_name);
      formData.append('institution', institution);

      if (proofDocument) {
        formData.append('proof_document', proofDocument);
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/register/teacher`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '註冊失敗');
      }

      const result = await response.json();
      handleSuccess(result.message || '註冊申請已送出，請等待管理員審核。');

      // 清空表單
      setTeacherForm({
        email: '',
        password: '',
        confirmPassword: '',
        full_name: '',
        school: '',
      });
      setProofDocument(null);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '註冊失敗，請稍後再試';
      handleError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-800">註冊</h2>
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

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <div className="flex">
            <button
              onClick={() => setActiveTab('student')}
              className={`flex-1 py-3 px-4 text-center font-medium transition-colors ${activeTab === 'student'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
                }`}
            >
              學生
            </button>
            <button
              onClick={() => setActiveTab('teacher')}
              className={`flex-1 py-3 px-4 text-center font-medium transition-colors ${activeTab === 'teacher'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
                }`}
            >
              教師
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {/* 成功訊息 */}
          {successMessage && (
            <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center">
              <svg
                className="w-5 h-5 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span>{successMessage}</span>
            </div>
          )}

          {/* 錯誤訊息 */}
          {errorMessage && (
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
              <span>{errorMessage}</span>
            </div>
          )}

          {/* 表單 */}
          {!successMessage && (
            <>
              {activeTab === 'student' ? (
                <RegisterForm onSuccess={handleSuccess} onError={handleError} />
              ) : (
                <form onSubmit={handleTeacherSubmit} className="space-y-4">
                  {/* 教師註冊提示 */}
                  <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg text-sm">
                    <p className="font-medium">⚠️ 教師註冊需經過管理員審核</p>
                    <p className="mt-1 text-xs">註冊後您的帳號將處於待審核狀態，審核通過後即可登入使用。</p>
                  </div>

                  {/* Email */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="email"
                      required
                      value={teacherForm.email}
                      onChange={(e) => setTeacherForm({ ...teacherForm, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="your.email@example.com"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* 密碼 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      密碼 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={teacherForm.password}
                      onChange={(e) => setTeacherForm({ ...teacherForm, password: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="至少 6 個字元"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* 確認密碼 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      確認密碼 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      required
                      value={teacherForm.confirmPassword}
                      onChange={(e) => setTeacherForm({ ...teacherForm, confirmPassword: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="再次輸入密碼"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* 姓名 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      姓名 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={teacherForm.full_name}
                      onChange={(e) => setTeacherForm({ ...teacherForm, full_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="請輸入真實姓名"
                      disabled={isSubmitting}
                    />
                  </div>

                  {/* 學校 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      學校 <span className="text-red-500">*</span>
                    </label>
                    <select
                      required
                      value={teacherForm.school}
                      onChange={(e) => setTeacherForm({ ...teacherForm, school: e.target.value as SchoolCode | '' })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={isSubmitting}
                    >
                      <option value="">請選擇學校</option>
                      {SCHOOLS.map((school) => (
                        <option key={school.code} value={school.code}>
                          {school.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* 證明文件 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      證明文件 <span className="text-gray-400">(可選)</span>
                    </label>
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(e) => setProofDocument(e.target.files?.[0] || null)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={isSubmitting}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      請上傳教師證、聘書或其他可證明教師身分的文件
                    </p>
                  </div>

                  {/* 提交按鈕 */}
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all ${isSubmitting
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:shadow-lg hover:-translate-y-0.5'
                      }`}
                  >
                    {isSubmitting ? '註冊中...' : '提交審核'}
                  </button>
                </form>
              )}
            </>
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
