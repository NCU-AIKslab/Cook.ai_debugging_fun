// frontend/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { UserProvider } from './contexts/UserContext';
import Home from './pages/Home';
import StudentPortal from './pages/Student';

import StudentPreCoding from './pages/student/debugging/StudentPreCoding';
import StudentCodingHelp from './pages/student/debugging/StudentCodingHelp';
import StudentProgress from './pages/teacher/StudentProgress';
import ProblemGeneration from './pages/teacher/ProblemGeneration';

function App() {
  return (
    <UserProvider>
      <Routes>
        <Route path="/" element={<Home />} />

        <Route path="/student" element={<StudentPortal />}>
          <Route index element={<Navigate to="/student/pre-coding" replace />} />
          <Route path="pre-coding" element={<StudentPreCoding />} />
          <Route path="coding-help" element={<StudentCodingHelp />} />
        </Route>

        <Route path="/teacher" element={<StudentPortal />}>
          <Route index element={<Navigate to="/teacher/student-progress" replace />} />
          <Route path="student-progress" element={<StudentProgress />} />
          <Route path="problem-generation" element={<ProblemGeneration />} />
        </Route>
      </Routes>
    </UserProvider>
  );
}

export default App;
