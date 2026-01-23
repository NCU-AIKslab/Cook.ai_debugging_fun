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

      <div className="flex flex-1 overflow-hidden">
        <StudentSidebar
          isSidebarOpen={isSidebarOpen}
          onToggle={toggleSidebar}
        />
        <main className="flex-1 overflow-hidden relative bg-gray-50">
          <Outlet />
        </main>
      </div>

      <div className="flex-shrink-0">
        <Footer />
      </div>
    </div>
  );
}

export default Student;