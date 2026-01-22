import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { FaChevronLeft, FaChalkboardTeacher } from 'react-icons/fa';
import { useUser } from '../../contexts/UserContext';
import API_BASE_URL from '../../config/api';

interface Course {
  id: number;
  name: string;
  semester: string;
}

interface TeacherSidebarProps {
  courseId?: string;
  isSidebarOpen: boolean;
  onToggle: () => void;
}

import CreateCourseModal from './CreateCourseModal';

function TeacherSidebar({ courseId, isSidebarOpen, onToggle }: TeacherSidebarProps) {
  const { user } = useUser();
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isTextVisible, setIsTextVisible] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Fetch courses function
  const fetchCourses = async () => {
    if (!user?.user_id) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/teachers/${user.user_id}/courses`);
      if (response.ok) {
        const data = await response.json();
        // Backend API returns: {id, name, semester, description, teacher_name}
        const mappedCourses = data.map((c: any) => ({
          id: c.id,
          name: c.name,  // 修正：後端回傳的是 name，不是 course_name
          semester: c.semester
        }));

        // 从 localStorage 获取课程顺序
        const savedOrder = localStorage.getItem(`teacher_${user.user_id}_course_order`);
        if (savedOrder) {
          try {
            const orderArray: number[] = JSON.parse(savedOrder);
            // 按保存的顺序排列课程
            const orderedCourses = orderArray
              .map(id => mappedCourses.find((c: any) => c.id === id))
              .filter(Boolean); // 移除已删除的课程
            // 添加新课程（不在保存顺序中的）
            const newCourses = mappedCourses.filter(
              (c: any) => !orderArray.includes(c.id)
            );
            setCourses([...orderedCourses, ...newCourses]);
          } catch (e) {
            setCourses(mappedCourses);
          }
        } else {
          setCourses(mappedCourses);
        }
      }
    } catch (error) {
      console.error('Failed to fetch teacher courses:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 保存课程顺序到 localStorage
  const saveCourseOrder = (orderedCourses: any[]) => {
    if (!user?.user_id) return;
    const orderArray = orderedCourses.map(c => c.id);
    localStorage.setItem(`teacher_${user.user_id}_course_order`, JSON.stringify(orderArray));
  };

  // Drag and drop handlers
  const [draggedCourseId, setDraggedCourseId] = useState<number | null>(null);
  const [dragOverCourseId, setDragOverCourseId] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, courseId: number) => {
    setDraggedCourseId(courseId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, courseId: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverCourseId(courseId);
  };

  const handleDragLeave = () => {
    setDragOverCourseId(null);
  };

  const handleDrop = (e: React.DragEvent, targetCourseId: number) => {
    e.preventDefault();

    if (!draggedCourseId || draggedCourseId === targetCourseId) {
      setDraggedCourseId(null);
      setDragOverCourseId(null);
      return;
    }

    const draggedIndex = courses.findIndex(c => c.id === draggedCourseId);
    const targetIndex = courses.findIndex(c => c.id === targetCourseId);

    if (draggedIndex === -1 || targetIndex === -1) return;

    const newCourses = [...courses];
    const [removed] = newCourses.splice(draggedIndex, 1);
    newCourses.splice(targetIndex, 0, removed);

    setCourses(newCourses);
    saveCourseOrder(newCourses);
    setDraggedCourseId(null);
    setDragOverCourseId(null);
  };

  const handleDragEnd = () => {
    setDraggedCourseId(null);
    setDragOverCourseId(null);
  };

  useEffect(() => {
    fetchCourses();
  }, [user?.user_id]);

  // Handle new course creation success
  const handleCourseCreated = () => {
    fetchCourses(); // Refresh list
    // Optionally navigate to new course? For now just refresh sidebar.
    // If we want to navigate, we need useNavigate here.
  };

  // Handle sidebar animation
  useEffect(() => {
    if (isSidebarOpen) {
      const timer = setTimeout(() => setIsTextVisible(true), 100);
      return () => clearTimeout(timer);
    } else {
      setIsTextVisible(false);
    }
  }, [isSidebarOpen]);

  return (
    <aside
      className={`
        h-full flex flex-col 
        bg-white border-r border-neutral-border flex-shrink-0 
        transition-[width] duration-300 ease-smooth 
        ${isSidebarOpen ? 'w-64' : 'w-16'}
      `}
    >
      {/* Header */}
      <div className={`px-4 py-4 border-b border-neutral-border flex items-center ${isSidebarOpen ? 'justify-between' : 'justify-center'}`}>
        {isSidebarOpen && (
          <div className="flex items-center gap-2">
            <FaChalkboardTeacher className="text-theme-primary" size={18} />
            <span className="font-semibold text-neutral-text-main text-sm">我的課程</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-2 rounded-lg text-neutral-icon hover:bg-gray-100 hover:text-neutral-icon-hover flex-shrink-0 transition-colors"
        >
          <FaChevronLeft className={`w-4 h-4 transition-transform duration-300 ${!isSidebarOpen && 'rotate-180'}`} />
        </button>
      </div>

      {/* Course List */}
      <div className="flex-1 overflow-y-auto py-3 px-2">
        <nav>
          <ul className="list-none p-0 m-0 space-y-1">
            {isLoading ? (
              <li className="px-3 py-2 text-sm text-neutral-text-tertiary text-center">
                載入中...
              </li>
            ) : courses.length === 0 ? (
              <li className="px-3 py-2 text-sm text-neutral-text-tertiary text-center">
                尚未開設課程
              </li>
            ) : (
              courses.map((course) => {
                const isActive = courseId === String(course.id);
                const isDragging = draggedCourseId === course.id;
                const isDragOver = dragOverCourseId === course.id;

                return (
                  <li
                    key={course.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, course.id)}
                    onDragOver={(e) => handleDragOver(e, course.id)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, course.id)}
                    onDragEnd={handleDragEnd}
                  >
                    <NavLink
                      to={`/teacher/courses/${course.id}`}
                      className={`
                        flex items-center gap-3 px-3 py-2.5 rounded-lg
                        no-underline transition-all duration-200 cursor-pointer
                        ${isActive
                          ? 'bg-gradient-to-r from-blue-50 to-teal-50 text-blue-700 border-l-3 border-blue-600'
                          : 'text-neutral-text-secondary hover:bg-gray-50 hover:text-neutral-text-main'
                        }
                        ${isDragging ? 'opacity-40' : ''}
                        ${isDragOver ? 'border-t-2 border-theme-primary' : ''}
                      `}
                    >
                      <div className={`
                        w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 font-semibold text-sm
                        ${isActive ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-neutral-text-secondary'}
                      `}>
                        {course.name.charAt(0)}
                      </div>

                      {isSidebarOpen && (
                        <div className={`flex-1 min-w-0 transition-opacity duration-150 ${isTextVisible ? 'opacity-100' : 'opacity-0'}`}>
                          <p className="text-sm font-medium truncate">{course.name}</p>
                          <p className="text-xs text-neutral-text-tertiary">{course.semester}</p>
                        </div>
                      )}
                    </NavLink>
                  </li>
                );
              })
            )}
          </ul>
        </nav>
      </div>

      {/* Footer - Add Course */}
      {isSidebarOpen && (
        <div className="px-3 py-3 border-t border-neutral-border">
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="w-full flex items-center justify-center gap-2 py-2 text-sm text-theme-primary hover:bg-theme-primary-light rounded-lg transition-colors font-medium"
          >
            + 新增課程
          </button>
        </div>
      )}

      <CreateCourseModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={handleCourseCreated}
      />
    </aside>
  );
}

export default TeacherSidebar;