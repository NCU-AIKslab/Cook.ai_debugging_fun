// frontend/src/pages/Student.tsx
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/common/Header';
import Footer from '../components/common/Footer.tsx';
import StudentSidebar from '../components/student/StudentSidebar';

function Student() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-white">
      <div className="flex-shrink-0">
        <Header paths={null} />
      </div>

      {/* Scrollable container for main content + footer */}
      <div className="flex-1 flex overflow-y-auto overflow-x-hidden">
        <StudentSidebar
          isSidebarOpen={isSidebarOpen}
          onToggle={toggleSidebar}
        />
        <div className="flex-1 flex flex-col min-h-full">
          <main className="flex-1 relative bg-gray-50">
            <Outlet />
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}

export default Student;