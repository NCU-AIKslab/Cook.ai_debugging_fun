// frontend/src/components/student/StudentSidebar.tsx
import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { FaBookOpen, FaPencilAlt, FaCode, FaChartBar, FaChevronLeft } from 'react-icons/fa';

interface StudentSidebarProps {
  courseId?: string;
  isSidebarOpen: boolean;
  onToggle: () => void;
}

function StudentSidebar({ courseId, isSidebarOpen, onToggle }: StudentSidebarProps) {
  const baseCoursePath = courseId ? `/student/course/${courseId}` : '/student';

  const [isTextVisible, setIsTextVisible] = useState(true);

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
    `flex items-center h-12 px-4 no-underline rounded-lg font-medium transition-all duration-200 ease-smooth
    ${isActive
      ? 'bg-theme-primary-light text-theme-primary-active border-l-3 border-theme-primary'
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
      <div className={`flex flex-col h-full ${isSidebarOpen ? 'px-6' : 'px-2'}`}>

        {/* Header with toggle */}
        <div
          className={`
            flex items-center mb-6 
            ${isSidebarOpen ? 'justify-between' : 'justify-center'}
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
            學生功能
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
            {courseId && (
              <>
                <li>
                  <NavLink to={`${baseCoursePath}/materials`} className={navLinkClass}>
                    <FaBookOpen className="flex-shrink-0 w-5 h-5" />
                    <span className={`whitespace-nowrap transition-opacity duration-150 text-sm ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                      課程教材
                    </span>
                  </NavLink>
                </li>
                <li>
                  <NavLink to={`${baseCoursePath}/assignments`} className={navLinkClass}>
                    <FaPencilAlt className="flex-shrink-0 w-5 h-5" />
                    <span className={`whitespace-nowrap transition-opacity duration-150 text-sm ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                      練習題與作業
                    </span>
                  </NavLink>
                </li>
                <li>
                  <NavLink to={`${baseCoursePath}/coding`} className={navLinkClass}>
                    <FaCode className="flex-shrink-0 w-5 h-5" />
                    <span className={`whitespace-nowrap transition-opacity duration-150 text-sm ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                      程式練習
                    </span>
                  </NavLink>
                </li>
                <li>
                  <NavLink to={`${baseCoursePath}/dashboard`} className={navLinkClass}>
                    <FaChartBar className="flex-shrink-0 w-5 h-5" />
                    <span className={`whitespace-nowrap transition-opacity duration-150 text-sm ${isTextVisible ? 'opacity-100' : 'opacity-0'} ${!isSidebarOpen && 'hidden'}`}>
                      學習儀表板
                    </span>
                  </NavLink>
                </li>
              </>
            )}
          </ul>
        </nav>
      </div>
    </aside>
  );
}

export default StudentSidebar;