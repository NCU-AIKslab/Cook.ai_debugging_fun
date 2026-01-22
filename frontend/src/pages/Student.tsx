import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/common/Header';
import Footer from '../components/common/Footer.tsx';

// Define the type for a single breadcrumb path item
interface BreadcrumbPath {
  name: string;
  path: string;
}

// Define the type for the Outlet context
interface OutletContext {
  setBreadcrumbPaths: React.Dispatch<React.SetStateAction<BreadcrumbPath[] | null>>;
  breadcrumbPaths: BreadcrumbPath[] | null;
}

function Student() {
  const [breadcrumbPaths, setBreadcrumbPaths] = useState<BreadcrumbPath[] | null>(null);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-white">

      <div className="flex-shrink-0">
        <Header paths={breadcrumbPaths} />
      </div>
      <main className="flex-1 overflow-hidden relative">
        <Outlet context={{ setBreadcrumbPaths, breadcrumbPaths } as OutletContext} />
      </main>
      <div className="flex-shrink-0">
        <Footer />
      </div>

    </div>
  );
}

export default Student;