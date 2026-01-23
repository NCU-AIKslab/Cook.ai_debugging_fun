// frontend/src/pages/Home.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../contexts/UserContext';
import { FaEye, FaEyeSlash, FaChevronLeft, FaChevronRight } from 'react-icons/fa';
import Footer from '../components/common/Footer';
import RegisterModal from '../components/auth/RegisterModal';
import API_BASE_URL from '../config/api';


function Home() {
  const navigate = useNavigate();
  const { setUser } = useUser();
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({ stu_id: '', stu_pwd: '' });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentSlide, setCurrentSlide] = useState(0);

  const features = [
    {
      title: 'AI 助教',
      description: '智慧生成教材與題目，協助自動批改，加快工作效率',
      image: '/images/ai_assistant.png',
      bgColor: 'from-blue-100 to-cyan-100',
      textBgColor: 'bg-gradient-to-r from-blue-500 to-cyan-500'
    },
    {
      title: '適性化學習',
      description: '適應每位學生的步調',
      image: '/images/adaptive_learning.png',
      bgColor: 'from-purple-100 to-pink-100',
      textBgColor: 'bg-gradient-to-r from-purple-500 to-pink-500'
    },
    {
      title: '學習分析',
      description: '即時追蹤學習進度，教師輕鬆了解學生學習成效',
      image: '/images/learning_analytics.png',
      bgColor: 'from-green-100 to-teal-100',
      textBgColor: 'bg-gradient-to-r from-green-500 to-teal-500'
    },
    {
      title: '互動學習',
      description: '程式練習與即時回饋',
      image: '/images/interactive_learning.png',
      bgColor: 'from-orange-100 to-red-100',
      textBgColor: 'bg-gradient-to-r from-orange-500 to-red-500'
    }
  ];

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % features.length);
  };

  const prevSlide = () => {
    setCurrentSlide((prev) => (prev - 1 + features.length) % features.length);
  };

  const getCardStyle = (index: number) => {
    const diff = index - currentSlide;
    const total = features.length;

    let normalizedDiff = diff;
    if (diff > total / 2) normalizedDiff = diff - total;
    if (diff < -total / 2) normalizedDiff = diff + total;

    if (normalizedDiff === 0) {
      return {
        transform: 'translateX(0%) scale(1)',
        opacity: 1,
        zIndex: 30
      };
    } else if (normalizedDiff === 1) {
      return {
        transform: 'translateX(70%) scale(0.85)',
        opacity: 0.6,
        zIndex: 20
      };
    } else if (normalizedDiff === -1) {
      return {
        transform: 'translateX(-70%) scale(0.85)',
        opacity: 0.6,
        zIndex: 20
      };
    } else {
      return {
        transform: normalizedDiff > 0 ? 'translateX(150%) scale(0.7)' : 'translateX(-150%) scale(0.7)',
        opacity: 0,
        zIndex: 10
      };
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
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

      const userData = {
        user_id: data.stu_id,
        full_name: data.stu_name,
        role: 'student'
      };

      localStorage.setItem('user', JSON.stringify(userData));
      setUser(userData);

      // 導向學生頁面
      navigate('/student');
    } catch (err: any) {
      setError(err.message || '登入失敗，請檢查您的學號密碼');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex flex-1 overflow-hidden">
        {/* Left Side - Branding & Features (2/3 width, White Background) */}
        <div className="hidden lg:flex lg:w-2/3 bg-white relative overflow-hidden">
          {/* Subtle background decoration */}
          <div className="absolute inset-0 bg-soft-gradient opacity-30"></div>

          <div className="relative z-10 flex flex-col justify-center items-center p-8 w-full">
            {/* Large Logo & Title with Gradient */}
            <div className="text-center mb-8">
              <h1 className="text-7xl font-bold mb-3 gradient-text animate-gradient pb-4">
                Cool Knowledge.ai
              </h1>
              <p className="text-lg text-gray-600 max-w-xl mx-auto">
                您的智慧教學夥伴，讓學習與教學更有效率
              </p>
            </div>

            {/* 3D Carousel Container - Square cards */}
            <div className="relative w-full max-w-2xl h-80">
              {/* Navigation Buttons */}
              <button
                onClick={prevSlide}
                className="absolute left-0 top-1/2 -translate-y-1/2 z-40 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-gray-50 transition-all -ml-5"
              >
                <FaChevronLeft className="text-gray-600 text-sm" />
              </button>

              <button
                onClick={nextSlide}
                className="absolute right-0 top-1/2 -translate-y-1/2 z-40 w-10 h-10 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-gray-50 transition-all -mr-5"
              >
                <FaChevronRight className="text-gray-600 text-sm" />
              </button>

              {/* Cards Container */}
              <div className="relative w-full h-full flex items-center justify-center">
                {features.map((feature, index) => {
                  const style = getCardStyle(index);
                  return (
                    <div
                      key={index}
                      className="absolute w-80 transition-all duration-500 ease-out"
                      style={style}
                    >
                      <div className="bg-white rounded-xl shadow-2xl overflow-hidden border border-gray-100 aspect-square flex flex-col">
                        <div className={`flex-1 bg-gradient-to-br ${feature.bgColor} overflow-hidden flex items-center justify-center`}>
                          <img
                            src={feature.image}
                            alt={feature.title}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div className={`p-4 ${feature.textBgColor}`}>
                          <h3 className="font-bold text-base text-white mb-1">{feature.title}</h3>
                          <p className="text-white text-xs leading-relaxed">{feature.description}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Dots Indicator */}
              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 flex justify-center gap-2">
                {features.map((_, index) => (
                  <button
                    key={index}
                    onClick={() => setCurrentSlide(index)}
                    className={`w-1.5 h-1.5 rounded-full transition-all ${index === currentSlide ? 'bg-blue-600 w-6' : 'bg-gray-300'}`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Side - Login Form (1/3 width, Dark Background) */}
        <div className="w-full lg:w-1/3 flex items-center justify-center p-8 bg-gradient-to-br from-slate-800 via-slate-700 to-slate-900 relative overflow-hidden">
          {/* Decorative background pattern */}
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-0 left-0 w-full h-full"
              style={{
                backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 35px, rgba(255,255,255,.05) 35px, rgba(255,255,255,.05) 70px)',
              }}>
            </div>
          </div>

          <div className="w-full max-w-sm relative z-10">
            {/* Mobile Logo */}
            <div className="lg:hidden mb-8 text-center">
              <h1 className="text-4xl font-bold gradient-text mb-2 pb-2">Cool Knowledge.ai</h1>
              <p className="text-gray-300">您的智慧教學夥伴</p>
            </div>

            <div className="mb-8">
              <h2 className="text-3xl font-bold text-white mb-2">登入</h2>
              <p className="text-gray-300">歡迎回來！請登入您的帳號</p>
            </div>

            {error && (
              <div className="mb-6 bg-red-500/10 border border-red-500/30 text-red-300 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  學號
                </label>
                <input
                  type="text"
                  required
                  value={form.stu_id}
                  onChange={(e) => setForm({ ...form, stu_id: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all placeholder-gray-500"
                  placeholder="請輸入學號"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  密碼
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={form.stu_pwd}
                    onChange={(e) => setForm({ ...form, stu_pwd: e.target.value })}
                    className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all pr-12 placeholder-gray-500"
                    placeholder="請輸入密碼"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200"
                  >
                    {showPassword ? <FaEyeSlash size={20} /> : <FaEye size={20} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 text-white py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-cyan-700 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? '登入中...' : '登入'}
              </button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-gray-400">
                還沒有帳號？{' '}
                <button
                  onClick={() => setIsRegisterModalOpen(true)}
                  className="text-blue-400 hover:text-blue-300 font-semibold hover:underline"
                >
                  立即註冊
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <Footer />

      {/* Register Modal */}
      <RegisterModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
      />

      <style>{`
@keyframes gradient {
  0 % { background- position: 0 % 50 %;
}
50 % { background- position: 100 % 50 %; }
100 % { background- position: 0 % 50 %; }
        }

        .animate - gradient {
  background - size: 200 % 200 %;
  animation: gradient 3s ease infinite;
}
`}</style>
    </div>
  );
}

export default Home;