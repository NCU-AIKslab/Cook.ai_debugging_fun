// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom';
import { UserProvider } from './contexts/UserContext';
import Home from './pages/Home';
import TeacherPortal from './pages/Teacher';
import StudentPortal from './pages/Student';

import TeacherCourseLayout from './components/teacher/TeacherCourseLayout';
import Courses from './pages/teacher/Courses';
import TeacherDashboard from './components/teacher/TeacherDashboard';

import StudentOverview from './pages/student/StudentOverview';
import StudentCourseLayout from './components/student/StudentCourseLayout';
import StudentCourseWeeks from './pages/student/StudentCourseWeeks';
import StudentCoding from './pages/student/debugging/StudentCoding';

function App() {
  return (
    <UserProvider>
      <Routes>
        <Route path="/" element={<Home />} />

        <Route path="/teacher" element={<TeacherPortal />}>
          <Route index element={<TeacherDashboard />} />
          <Route path="courses/:courseId" element={<TeacherCourseLayout />}>
            <Route index element={<Courses />} />
          </Route>
        </Route>

        <Route path="/student" element={<StudentPortal />}>
          <Route index element={<StudentOverview />} />
          <Route path="course/:courseId" element={<StudentCourseLayout />}>
            <Route index element={<StudentCourseWeeks />} />
            <Route path="materials" element={<h2>課程教材 (待開發)</h2>} />
            <Route path="assignments" element={<h2>練習題與作業 (待開發)</h2>} />
            <Route path="coding" element={<StudentCoding />} />
            <Route path="dashboard" element={<h2>學習儀表板 (待開發)</h2>} />
          </Route>
        </Route>
      </Routes>
    </UserProvider>
  );
}

export default App;
