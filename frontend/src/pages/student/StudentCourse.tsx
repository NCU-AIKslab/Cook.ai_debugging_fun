import { useEffect } from 'react'; // 1. 引入 useEffect
import { useOutletContext, useParams } from 'react-router-dom';

// 定義 Context 介面 (確保跟 Layout 一致)
interface OutletContext {
  setBreadcrumbPaths: React.Dispatch<React.SetStateAction<Array<{ name: string; path: string }> | null>>;
  breadcrumbPaths: Array<{ name: string; path: string }> | null;
}

function StudentCourse() {
  const { courseId } = useParams();

  // 2. 修正之前的 typo，正確取得 context
  const { setBreadcrumbPaths } = useOutletContext<OutletContext>();

  // 3. 加入這段 Effect：當使用者來到這個頁面時，強制重置麵包屑為「只有兩層」
  useEffect(() => {
    if (setBreadcrumbPaths && courseId) {
      setBreadcrumbPaths([
        { name: '學生總覽', path: '/student' },
        { name: '課程', path: `/student/course/${courseId}` },
        // 這裡不放第三層，這樣原本的 "程式練習" 就會被這裡的設定覆蓋掉 (消失)
      ]);
    }
  }, [courseId, setBreadcrumbPaths]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">課程內容</h2>
      </div>

      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 min-h-[400px]">
        <h3 className="text-xl font-semibold mb-4">此區塊待開發...</h3>
        <p className="text-gray-500">
          這裡是點擊「課程教材」、「練習題與作業」等其他連結時顯示的預設畫面。
        </p>
      </div>
    </div>
  );
}

export default StudentCourse;