// frontend/src/components/student/StudentCourseLayout.tsx
import { useEffect, useState } from 'react';
import { Outlet, useParams, useOutletContext, useLocation } from 'react-router-dom';
import StudentSidebar from './StudentSidebar';

interface OutletContext {
  setBreadcrumbPaths: React.Dispatch<React.SetStateAction<Array<{ name: string; path: string }> | null>>;
  breadcrumbPaths: Array<{ name: string; path: string }> | null;
}

const BREADCRUMB_MAP: Record<string, string> = {
  'coding': '程式練習',
};

function StudentCourseLayout() {
  const { courseId } = useParams();
  const context = useOutletContext<OutletContext>();
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  useEffect(() => {
    if (context.setBreadcrumbPaths && courseId) {
      const currentPath = location.pathname.split('/').pop() || '';
      const pageName = BREADCRUMB_MAP[currentPath];

      const basePaths = [
        { name: '學生總覽', path: '/student' },
        { name: '課程', path: `/student/course/${courseId}` },
      ];

      if (pageName) {
        context.setBreadcrumbPaths([...basePaths, { name: pageName, path: location.pathname }]);
      } else {
        context.setBreadcrumbPaths(basePaths);
      }
    }
  }, [courseId, context.setBreadcrumbPaths, location]);

  return (
    <div className="flex h-full w-full overflow-hidden bg-white">
      <div className="flex flex-1 overflow-hidden">

        <StudentSidebar
          courseId={courseId}
          isSidebarOpen={isSidebarOpen}
          onToggle={toggleSidebar}
        />
        <main className="flex-1 overflow-y-auto relative bg-gray-50">
          <div className="p-8 min-h-full">
            <Outlet context={context} />
          </div>
        </main>
      </div>

    </div>
  );
}

export default StudentCourseLayout;