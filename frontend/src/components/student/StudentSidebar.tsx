// frontend/src/components/student/StudentSidebar.tsx
import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { FaCode, FaChevronLeft, FaChevronDown, FaChevronRight, FaChartBar } from 'react-icons/fa';
import { useUser } from '../../contexts/UserContext';

interface StudentSidebarProps {
  isSidebarOpen: boolean;
  onToggle: () => void;
}

function StudentSidebar({ isSidebarOpen, onToggle }: StudentSidebarProps) {
  const location = useLocation();
  const { user } = useUser();
  const [isTextVisible, setIsTextVisible] = useState(true);
  const [isProgrammingOpen, setIsProgrammingOpen] = useState(true);

  // Check if current path is under programming section
  const isProgrammingActive = location.pathname.includes('/student/pre-coding') ||
    location.pathname.includes('/student/coding-help');

  const isTeacher = user?.role === 'teacher';

  console.log('[SidebarDebug] User:', user);
  console.log('[SidebarDebug] Role string:', user?.role, 'isTeacher bool:', isTeacher);

  useEffect(() => {
    if (isSidebarOpen) {
      const timer = setTimeout(() => {
        setIsTextVisible(true);
      }, 100);
      return () => clearTimeout(timer);
    } else {
      setIsTextVisible(false);
    }
  }, [isSidebarOpen]);

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center h-10 px-4 no-underline rounded-lg font-medium transition-all duration-200 ease-smooth text-sm
    ${isActive
      ? 'bg-theme-primary-light text-theme-primary-active border-l-3 border-theme-primary'
      : 'text-neutral-text-secondary hover:bg-theme-surface-hover hover:text-theme-primary'
    }
    ${isSidebarOpen ? 'gap-3 pl-10' : 'justify-center'}`;

  // Style for top-level links (like the Programming toggler)
  const topLevelLinkClass = ({ isActive }: { isActive: boolean }) => `flex items-center h-12 px-4 no-underline rounded-lg font-medium transition-all duration-200 ease-smooth cursor-pointer
    ${isActive
      ? 'bg-blue-50 text-blue-700'
      : 'text-neutral-text-secondary hover:bg-theme-surface-hover hover:text-theme-primary'
    }
    ${isSidebarOpen ? 'gap-3' : 'justify-center'}`;

  const parentMenuClass = `flex items-center h-12 px-4 no-underline rounded-lg font-medium transition-all duration-200 ease-smooth cursor-pointer
    ${isProgrammingActive
      ? 'bg-blue-50 text-blue-700'
      : 'text-neutral-text-secondary hover:bg-theme-surface-hover hover:text-theme-primary'
    }
    ${isSidebarOpen ? 'gap-3' : 'justify-center'}`;

  return (
    <aside
      className={`
        bg-white border-r border-neutral-border py-6 flex-shrink-0
        transition-[width] duration-300 ease-smooth h-full
        ${isSidebarOpen ? 'w-64' : 'w-20'} 
      `}
    >
      <div className={`flex flex-col h-full ${isSidebarOpen ? 'px-4' : 'px-2'}`}>

        {/* Header with toggle */}
        <div
          className={`
            flex items-center mb-6 
            ${isSidebarOpen ? 'justify-between px-2' : 'justify-center'}
          `}
        >
          <h3
            className={`
              text-lg font-semibold text-neutral-text-main whitespace-nowrap overflow-hidden
              transition-opacity duration-150
              ${isTextVisible ? 'opacity-100' : 'opacity-0'}
              ${!isSidebarOpen && 'hidden'}
            `}
          >
            {isTeacher ? '教師功能' : '學生功能'}
          </h3>

          <button
            onClick={onToggle}
            className="p-2 rounded-lg text-neutral-icon hover:bg-theme-surface-hover hover:text-neutral-icon-hover flex-shrink-0 focus:outline-none transition-colors duration-200"
            title={isSidebarOpen ? "收起選單" : "展開選單"}
          >
            <FaChevronLeft
              className={`w-5 h-5 transition-transform duration-300 ${!isSidebarOpen && 'rotate-180'}`}
            />
          </button>
        </div>

        <nav>
          <ul className="list-none p-0 m-0 space-y-1">

            {/* [Teacher Only] Student Progress */}
            {isTeacher && (
              <li>
                <NavLink to="/teacher/student-progress" className={topLevelLinkClass}>
                  <FaChartBar className="flex-shrink-0 w-5 h-5" />
                  <span className={`flex-1 whitespace-nowrap transition-opacity duration-150 ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                    學生答題情況
                  </span>
                </NavLink>
              </li>
            )}

            {/* 程式練習 - Parent Menu */}
            <li>
              <div
                className={parentMenuClass}
                onClick={() => isSidebarOpen && setIsProgrammingOpen(!isProgrammingOpen)}
              >
                <FaCode className="flex-shrink-0 w-5 h-5" />
                <span className={`flex-1 whitespace-nowrap transition-opacity duration-150 ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                  程式練習
                </span>
                {isSidebarOpen && (
                  <span className="text-gray-400">
                    {isProgrammingOpen ? <FaChevronDown className="w-3 h-3" /> : <FaChevronRight className="w-3 h-3" />}
                  </span>
                )}
              </div>

              {/* Sub-items */}
              {isSidebarOpen && isProgrammingOpen && (
                <ul className="list-none p-0 m-0 mt-1 space-y-1">
                  <li>
                    <NavLink to="/student/pre-coding" className={navLinkClass}>
                      <span className={`whitespace-nowrap transition-opacity duration-150 ${isTextVisible ? 'opacity-100' : 'opacity-0'}`}>
                        Pre-Coding
                      </span>
                    </NavLink>
                  </li>
                  <li>
                    <NavLink to="/student/coding-help" className={navLinkClass}>
                      <span className={`whitespace-nowrap transition-opacity duration-150 ${isTextVisible ? 'opacity-100' : 'opacity-0'}`}>
                        CodingHelp
                      </span>
                    </NavLink>
                  </li>
                </ul>
              )}
            </li>
          </ul>
        </nav>
      </div>
    </aside>
  );
}

export default StudentSidebar;