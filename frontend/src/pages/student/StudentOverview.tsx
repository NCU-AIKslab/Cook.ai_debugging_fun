// frontend/src/pages/student/StudentOverview.tsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import InfoBlock from '../../components/common/InfoBlock';
import Spinner from '../../components/common/Spinner';

// Define a type for the course object
interface Course {
  id: number;
  name: string;
  semester_name: string;
  description: string | null;
  teacher_name: string;
}

/**
 * ============================================================================
 * 課程可用性配置 (Course Availability Configuration)
 * ============================================================================
 * 
 * 這裡定義哪些課程已經開發完成可以點擊進入。
 * 其他開發者可以在這裡新增已完成的課程名稱。
 * 
 * 使用方式：
 * 1. 當你完成某個課程的週次頁面開發後，將課程名稱加入此陣列
 * 2. 例如：完成「程式設計-Python」後，加入 '程式設計-Python'
 * 
 * 前端路由端點：
 * - 課程週次頁面: /student/course/:courseId
 * - 對應組件: StudentCourseWeeks.tsx
 * - API 端點: GET /api/courses/:courseId
 */
const AVAILABLE_COURSES: string[] = [
  '人工智慧教育應用概論',
  // '程式設計-Python',
  // '智慧型網路服務工程',
];


function StudentOverview() {
  const announcements: any[] = [];
  const events: any[] = [];
  const materials: any[] = [];

  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 從 API 取得課程列表
  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('http://localhost:8000/api/courses');

        if (!response.ok) {
          throw new Error('無法取得課程列表');
        }

        const data = await response.json();
        setCourses(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '發生錯誤');
        console.error('取得課程失敗:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCourses();
  }, []);

  return (
    <div className="px-16 pt-8 pb-8 flex flex-col bg-neutral-background min-h-full">

      <h3 className="mb-6 border-b border-neutral-border pb-4 text-neutral-text-main font-bold">
        我的課程
      </h3>

      {isLoading ? (
        <div className="py-12">
          <Spinner />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-default">
          {error}
        </div>
      ) : courses.length === 0 ? (
        <div className="text-center py-12 text-neutral-text-secondary">
          目前沒有課程
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-6">
          {courses.map((course) => {
            // const isAvailable = isCourseAvailable(course.name); // 已不再使用

            // ============================================================================
            // 課程卡片渲染邏輯
            // ============================================================================
            // 如果課程已開發完成 (在 AVAILABLE_COURSES 中)，則渲染可點擊的 Link
            // 如果課程尚未開發，則渲染 div 但外觀相同（無法點擊）
            // 
            // [開發者注意] 
            // 當你完成新課程的開發後，請將課程名稱加入上方的 AVAILABLE_COURSES 陣列
            // 路由端點: /student/course/:courseId → StudentCourseWeeks.tsx
            // ============================================================================

            if (course.name === '人工智慧教育應用概論') {
              // 只讓「人工智慧教育應用概論」可點擊
              return (
                <Link
                  to={`/student/course/${course.id}`}
                  key={course.id}
                  className="
                    block 
                    border border-neutral-border
                    rounded-default
                    p-6 
                    transition-all duration-200 ease-in-out 
                    no-underline 
                    text-neutral-text-main 
                    bg-white 
                    shadow-default
                    hover:-translate-y-1 
                    hover:shadow-lg
                    hover:border-theme-primary
                    group
                  "
                >
                  <h4 className="mt-0 text-xl text-theme-primary transition-colors group-hover:text-theme-primary-hover">
                    {course.name}
                  </h4>
                  <p className="text-sm text-neutral-text-secondary mb-1">{course.teacher_name}</p>
                  <p className="text-xs text-neutral-text-tertiary mb-0">學期：{course.semester_name}</p>
                </Link>
              );
            }
            // 其他課程：不可點擊但外觀一致
            return (
              <div
                key={course.id}
                className="
                    block 
                    border border-neutral-border
                    rounded-default
                    p-6 
                    transition-all duration-200 ease-in-out 
                    no-underline 
                    text-neutral-text-main 
                    bg-white 
                    shadow-default
                    hover:-translate-y-1 
                    hover:shadow-lg
                    hover:border-theme-primary
                    group
                "
              >
                <h4 className="mt-0 text-xl text-theme-primary transition-colors group-hover:text-theme-primary-hover">
                  {course.name}
                </h4>
                <p className="text-sm text-neutral-text-secondary mb-1">{course.teacher_name}</p>
                <p className="text-xs text-neutral-text-tertiary mb-0">學期：{course.semester_name}</p>
              </div>
            );
          })}
        </div>
      )}

      <InfoBlock title="最新公告" items={announcements} />
      <InfoBlock title="最近教材" items={events} />
      <InfoBlock title="最近事件 (未完成)" items={materials} />
    </div>
  );
}

export default StudentOverview;