// API 基礎 URL 配置
// 如果環境變數沒有正確加載，可以直接在這裡修改

// const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE_URL = 'https://api.coolknowledge.ai/debugging-backend';

console.log('API_BASE_URL loaded:', API_BASE_URL); // 除錯用

export default API_BASE_URL;
