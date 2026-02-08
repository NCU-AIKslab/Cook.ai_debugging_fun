import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import Breadcrumb from './Breadcrumb';

interface HeaderProps {
  paths: Array<{ name: string; path: string }> | null;
}

function Header({ paths }: HeaderProps) {
  const navigate = useNavigate();
  const { user } = useUser();

  const handleLogout = () => {
    navigate('/');
  };

  // Display "XXX教師" for teachers, otherwise just the name
  const displayName = user?.role === 'teacher'
    ? `${user.full_name}教師`
    : (user?.full_name || '訪客');

  return (
    <header className="h-[60px] bg-white border-b border-neutral-border px-8 flex items-center justify-between flex-shrink-0 shadow-sm">
      <div className="flex items-center gap-6">
        {/* Cook.ai Logo */}
        <div className="text-2xl font-bold gradient-text">
          Cook.debugging
        </div>

        {/* Breadcrumb */}
        {paths && paths.length > 0 && <Breadcrumb paths={paths} />}
      </div>
      <div className="flex items-center gap-4">
        {/* User name */}
        <span className="text-neutral-text-secondary font-medium">{displayName}</span>

        {/* Logout button */}
        <button
          className="
            bg-destructive text-white border-none py-2 px-4 
            rounded-lg font-medium
            cursor-pointer transition-all duration-200
            hover:bg-destructive-hover hover:-translate-y-0.5
            focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-2
          "
          onClick={handleLogout}
        >
          Logout
        </button>
      </div>
    </header>
  );
}

export default Header;