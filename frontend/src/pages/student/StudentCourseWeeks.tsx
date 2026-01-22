// frontend/src/pages/student/StudentCourseWeeks.tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { FaBell, FaChevronDown, FaChevronRight, FaBookOpen, FaClipboardCheck, FaFileAlt } from 'react-icons/fa';
import Spinner from '../../components/common/Spinner';

// 課程單元介面
interface CourseUnit {
  id: number;
  week: number;
  chapter_name: string;
  display_order: number;
}

// 課程詳情介面
interface CourseDetail {
  id: number;
  name: string;
  semester_name: string;
  description: string | null;
  teacher_name: string;
  units: CourseUnit[];
}

// 公告介面
interface Announcement {
  id: number;
  title: string;
  date: string;
}

function StudentCourseWeeks() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedWeeks, setExpandedWeeks] = useState<number[]>([]);

  // 模擬公告資料（未來可從 API 取得）
  const announcements: Announcement[] = [
    { id: 1, title: "Syllabus.pdf 更新公告", date: "2025-12-08" }
  ];

  // 從 API 取得課程詳情（含週次單元）
  useEffect(() => {
    const fetchCourseDetail = async () => {
      if (!courseId) return;

      try {
        setIsLoading(true);
        const response = await fetch(`http://localhost:8000/api/courses/${courseId}`);

        if (!response.ok) {
          throw new Error('無法取得課程資訊');
        }

        const data = await response.json();
        setCourse(data);

        // 預設展開第一週
        if (data.units && data.units.length > 0) {
          setExpandedWeeks([data.units[0].week]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '發生錯誤');
        console.error('取得課程詳情失敗:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCourseDetail();
  }, [courseId]);

  // 切換週次展開/收合
  const toggleWeek = (week: number) => {
    setExpandedWeeks(prev =>
      prev.includes(week)
        ? prev.filter(w => w !== week)
        : [...prev, week]
    );
  };

  if (isLoading) {
    return (
      <div className="py-12 flex justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-destructive-light border border-destructive text-destructive px-4 py-3 rounded-lg">
        {error}
      </div>
    );
  }

  if (!course) {
    return (
      <div className="text-center py-12 text-neutral-text-tertiary">
        課程不存在
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 最新公告區塊 */}
      <div className="bg-white rounded-xl border border-neutral-border p-6 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <FaBell className="text-theme-primary" size={20} />
          <h2 className="text-lg font-semibold text-neutral-text-main">最新公告</h2>
        </div>

        {announcements.length > 0 ? (
          <div className="space-y-3">
            {announcements.map((announcement) => (
              <div
                key={announcement.id}
                className="bg-theme-primary-light rounded-lg p-4 border border-theme-border-light flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-theme-primary"></div>
                  <div>
                    <p className="font-medium text-neutral-text-main">{announcement.title}</p>
                    <p className="text-theme-primary text-sm">{announcement.date}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-neutral-text-tertiary italic">目前沒有公告</p>
        )}
      </div>

      {/* Course content header */}
      <h2 className="text-lg font-semibold text-neutral-text-main">課程內容</h2>

      {/* 週次列表 */}
      {course.units.length === 0 ? (
        <div className="text-center py-12 text-neutral-text-tertiary bg-white rounded-xl border border-neutral-border">
          此課程尚未設定週次單元
        </div>
      ) : (
        <div className="space-y-3">
          {course.units.map((unit) => {
            const isExpanded = expandedWeeks.includes(unit.week);

            return (
              <div
                key={unit.id}
                className={`bg-white rounded-xl transition-all duration-200 ${isExpanded
                  ? 'border-2 border-theme-primary shadow-card-hover'
                  : 'border border-neutral-border hover:border-neutral-icon shadow-card'
                  }`}
              >
                {/* 週次標題列 (可點擊) */}
                <div
                  onClick={() => toggleWeek(unit.week)}
                  className="px-6 py-5 flex items-center justify-between cursor-pointer select-none"
                >
                  <div>
                    <div className={`text-base font-semibold ${isExpanded ? 'text-theme-primary' : 'text-neutral-text-main'}`}>
                      Topic {unit.week}: {unit.chapter_name}
                    </div>
                  </div>
                  {isExpanded ? (
                    <FaChevronDown className="text-neutral-text-tertiary" size={14} />
                  ) : (
                    <FaChevronRight className="text-neutral-text-tertiary" size={14} />
                  )}
                </div>

                {/* 展開的內容區塊 */}
                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-neutral-border pt-6">
                    {/* 學習知識點描述 */}
                    <p className="text-neutral-text-secondary text-sm mb-6">
                      學習知識點：{unit.chapter_name}相關內容
                    </p>

                    {/* 統計標籤 */}
                    <div className="flex flex-wrap gap-3 mb-6">
                      <div className="flex items-center gap-1.5 text-neutral-text-secondary text-sm bg-gray-100 px-3 py-1.5 rounded-md">
                        <FaFileAlt size={14} className="text-neutral-text-tertiary" />
                        <span className="font-medium text-neutral-text-main">1份教材</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-sm bg-theme-primary-light px-3 py-1.5 rounded-lg">
                        <FaBookOpen size={12} className="text-theme-primary" />
                        <span className="font-medium text-theme-primary-active">課前預習&檢核</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-sm bg-theme-accent-light px-3 py-1.5 rounded-lg">
                        <FaClipboardCheck size={12} className="text-theme-accent" />
                        <span className="font-medium text-theme-accent-hover">課後複習&檢核</span>
                      </div>
                    </div>

                    {/* 學習項目列表 (模擬資料，未來可從 API 取得) */}
                    <div className="space-y-0 divide-y divide-neutral-border">
                      <div className="py-4 flex items-center justify-between group hover:bg-theme-surface-hover px-3 -mx-3 rounded-lg transition-colors">
                        <div className="flex items-center gap-4">
                          <div className="w-5 h-5 rounded-full border-2 border-neutral-border flex items-center justify-center flex-shrink-0">
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="text-neutral-text-tertiary text-xs">[課前閱讀]</span>
                              <span className="font-medium text-neutral-text-main text-sm">{unit.chapter_name}定義</span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-neutral-text-tertiary">
                              <span className="bg-theme-primary-light text-theme-primary-active px-2 py-0.5 rounded font-medium">
                                課前預習
                              </span>
                              <span>5 min</span>
                            </div>
                          </div>
                        </div>
                        <button className="text-theme-primary font-medium text-sm hover:underline whitespace-nowrap px-3 py-1.5 rounded-lg hover:bg-theme-primary-light transition-colors">
                          開始學習
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default StudentCourseWeeks;
