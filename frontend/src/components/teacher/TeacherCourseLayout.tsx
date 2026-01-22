import { useEffect, useState } from 'react';
import { Outlet, useParams, useOutletContext } from 'react-router-dom';
import TeacherSidebar from './TeacherSidebar';

// Define the type for the Outlet context
interface OutletContext {
  setBreadcrumbPaths: React.Dispatch<React.SetStateAction<Array<{ name: string; path: string }> | null>>;
  breadcrumbPaths: Array<{ name: string; path: string }> | null;
}

/**
 * TeacherCourseLayout - Course-Structured approach with course selector sidebar
 */
function TeacherCourseLayout() {
  const { courseId } = useParams();
  const context = useOutletContext<OutletContext>();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  useEffect(() => {
    if (context?.setBreadcrumbPaths && courseId) {
      // Only show course name, not full path
      context.setBreadcrumbPaths([
        { name: '我的課程', path: `/teacher/courses/${courseId}` },
      ]);
    }
  }, [courseId, context?.setBreadcrumbPaths]);

  return (
    <div className="flex h-full">
      {/* Course Selector Sidebar */}
      <TeacherSidebar
        isSidebarOpen={isSidebarOpen}
        onToggle={toggleSidebar}
        courseId={courseId}
      />

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-soft-gradient">
        <Outlet context={context} />
      </main>
    </div>
  );
}

export default TeacherCourseLayout;