# 2026-01-06 工作日誌：登入系統整合與首頁重新設計

## 日期
2026-01-06

## 工作概述
完成了登入系統的整合與首頁的全面重新設計，包括建立統一的認證入口、實作 3D 輪播卡片展示特色功能，以及優化整體使用者體驗。

---

## 主要完成項目

### 1. 登入系統整合

#### 1.1 後端 API 實作
**檔案**：`backend/app/routers/course_router.py`

- 實作 `POST /api/auth/login` 端點
- 新增 `LoginRequest` 和 `LoginResponse` Pydantic 模型
- 實作密碼驗證功能（使用 Argon2）
- 返回完整使用者資訊（user_id, email, full_name, role）

```python
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: str
```

#### 1.2 前端認證流程
**新增檔案**：
- `frontend/src/contexts/UserContext.tsx` - 全域使用者狀態管理
- `frontend/src/components/auth/LoginModal.tsx` - 登入彈窗組件（後來整合到 Home）

**功能特點**：
- 使用 Context API 管理全域登入狀態
- localStorage 持久化使用者資訊
- 自動根據角色導向（teacher/student）
- 提供 `useUser()` hook 供其他組件使用

#### 1.3 整合到課程頁面
**檔案**：`frontend/src/pages/teacher/TeacherCourseDetail.tsx`

- 使用 `useUser()` hook 取得當前登入使用者
- 建立公告時自動使用登入教師的 `user_id`
- 確保只有登入使用者才能執行操作

---

### 2. 首頁全面重新設計

#### 2.1 設計演進過程

**階段 1：初始整合**
- 將登入/註冊按鈕移到右上角
- 保留原有的教師/學生入口分離設計

**階段 2：統一入口**
- 移除教師/學生分離入口
- 改為統一的登入/註冊按鈕
- 登入後自動根據角色導向

**階段 3：LangChain 風格分屏布局**
- 採用左右分屏設計（2:1 比例）
- 左側：品牌展示 + 特色功能
- 右側：登入表單（深色背景）

**階段 4：3D 輪播卡片**
- 實作層疊式輪播效果
- 中間卡片完整顯示，左右卡片縮小在背後
- 平滑的過渡動畫

**階段 5：視覺優化**
- 調整為正方形卡片
- 圖片滿版顯示
- 為文字區域添加彩色漸層背景

#### 2.2 最終設計特點

**左側（品牌展示區）**：
- 超大標題：`Cool Knowledge.ai`（text-7xl）
- 副標題：「您的智慧教學夥伴，讓學習與教學更有效率」
- 3D 輪播卡片展示 4 大特色功能
- 柔和的背景漸層裝飾

**右側（登入區）**：
- 深灰色漸層背景（`from-slate-800 via-slate-700 to-slate-900`）
- 斜線紋理裝飾
- Email 和密碼輸入框
- 密碼顯示/隱藏切換
- 漸層登入按鈕
- 註冊連結

**3D 輪播卡片功能**：
- 一次顯示 3 張卡片（中間 1 張大，左右各 1 張小）
- 左右箭頭導航
- 底部圓點指示器
- 500ms 平滑過渡動畫
- 自動循環播放

#### 2.3 特色功能卡片內容更新

**AI 助教**：
- 描述：智慧生成教材與題目，協助自動批改，加快工作效率
- 配色：藍色到青色漸層

**適性化學習**：
- 描述：適應每位學生的步調
- 配色：紫色到粉色漸層

**學習分析**：
- 描述：即時追蹤學習進度，教師輕鬆了解學生學習成效
- 配色：綠色到青綠色漸層

**互動學習**：
- 描述：程式練習與即時回饋
- 配色：橙色到紅色漸層

#### 2.4 圖片資源
**生成並使用的 AI 圖片**：
- `ai_assistant.png` - AI 助教插圖
- `adaptive_learning.png` - 適性化學習插圖
- `learning_analytics.png` - 學習分析插圖
- `interactive_learning.png` - 互動學習插圖（保留原有）

所有圖片存放於 `frontend/public/images/`

---

### 3. 程式碼清理

#### 3.1 移除冗餘檔案
- 刪除 `frontend/src/pages/Login.tsx`（功能已整合到 Home）
- 從 `App.tsx` 移除 `/login` 路由
- 移除 `Login` 組件的 import

#### 3.2 路由簡化
**更新前**：
```typescript
<Route path="/" element={<Home />} />
<Route path="/login" element={<Login />} />
```

**更新後**：
```typescript
<Route path="/" element={<Home />} />
// 登入功能已整合到 Home，不需要獨立路由
```

---

## 技術實作細節

### 1. 3D 輪播效果實作

**核心邏輯**：
```typescript
const getCardStyle = (index: number) => {
  const diff = index - currentSlide;
  
  if (normalizedDiff === 0) {
    // 中間卡片：完整大小
    return { transform: 'translateX(0%) scale(1)', opacity: 1, zIndex: 30 };
  } else if (normalizedDiff === 1) {
    // 右側卡片：縮小到 85%
    return { transform: 'translateX(70%) scale(0.85)', opacity: 0.6, zIndex: 20 };
  } else if (normalizedDiff === -1) {
    // 左側卡片：縮小到 85%
    return { transform: 'translateX(-70%) scale(0.85)', opacity: 0.6, zIndex: 20 };
  }
  // 其他卡片：隱藏
};
```

### 2. 響應式設計

**桌面版**（lg 以上）：
- 左右分屏布局（2:1）
- 顯示完整輪播卡片

**手機版**：
- 單欄布局
- 顯示簡化的登入表單
- 隱藏品牌展示區

### 3. 視覺設計系統

**顏色配置**：
```typescript
features = [
  { 
    bgColor: 'from-blue-100 to-cyan-100',
    textBgColor: 'bg-gradient-to-r from-blue-500 to-cyan-500'
  },
  // ... 其他特色
]
```

**尺寸規格**：
- 卡片：正方形（aspect-square），寬度 320px
- 輪播容器：高度 320px
- 圖片：滿版顯示（object-cover）

---

## 檔案變更清單

### 新增檔案
- `frontend/src/contexts/UserContext.tsx`
- `frontend/src/components/auth/LoginModal.tsx`（後來未使用）
- `frontend/public/images/ai_assistant.png`
- `frontend/public/images/adaptive_learning.png`
- `frontend/public/images/learning_analytics.png`

### 修改檔案
- `backend/app/routers/course_router.py` - 新增登入 API
- `frontend/src/pages/Home.tsx` - 完全重新設計
- `frontend/src/App.tsx` - 整合 UserProvider，移除 /login 路由
- `frontend/src/pages/teacher/TeacherCourseDetail.tsx` - 整合 useUser hook

### 刪除檔案
- `frontend/src/pages/Login.tsx`

---

## 使用者體驗改進

### 登入流程
**之前**：
1. 訪問首頁
2. 點擊「教師平台」或「學生平台」
3. 被導向到 `/login` 頁面
4. 登入後手動選擇平台

**現在**：
1. 訪問首頁即可看到登入表單
2. 輸入帳號密碼登入
3. 系統自動根據角色導向對應平台
4. 更直觀、更快速

### 視覺呈現
- 從靜態卡片改為動態 3D 輪播
- 增加彩色漸層背景，視覺更豐富
- 圖片滿版顯示，更有衝擊力
- 整體設計更現代、更專業

---

## 待處理事項

### 1. 註冊與角色管理
**討論中的方案**：
- 首頁註冊僅支援學生註冊
- 教師帳號由 Admin 建立，或使用 Email domain 白名單驗證
- 需要實作 Email 驗證流程
- 可能需要開發 Admin 審核介面

### 2. 路由保護
- 實作 Protected Route 組件
- 確保未登入使用者無法訪問教師/學生平台
- 登入後根據角色限制訪問權限

### 3. 圖片優化
- 考慮為正方形卡片重新生成更適合的圖片
- 優化圖片載入效能

---

## 技術債務

1. **LoginModal 組件未使用**：已建立但最終整合到 Home，可考慮刪除
2. **Email 驗證流程**：後端已實作但前端未完整整合
3. **錯誤處理**：登入錯誤訊息可以更詳細（如：帳號不存在 vs 密碼錯誤）

---

## 學習與心得

1. **設計迭代的重要性**：經過多次調整才達到理想的視覺效果
2. **使用者體驗優先**：將登入整合到首頁大幅簡化了使用流程
3. **3D 效果實作**：透過 transform 和 z-index 實現層疊輪播效果
4. **Context API 應用**：有效管理全域認證狀態

---

## 下一步計畫

1. 確定註冊與角色管理的最終方案
2. 實作 Email domain 白名單驗證（如採用）
3. 開發 Protected Route 機制
4. 完善錯誤處理和使用者提示
5. 進行完整的登入/註冊流程測試
