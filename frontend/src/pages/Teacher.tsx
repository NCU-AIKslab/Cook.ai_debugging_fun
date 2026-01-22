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

function Teacher() {
  // 建立 state 來管理麵包屑，並指定型別
  const [breadcrumbPaths, setBreadcrumbPaths] = useState<BreadcrumbPath[] | null>(null);

  return (
    <div className="flex flex-col h-screen">
      <Header paths={breadcrumbPaths} />
      <main className="flex-1 overflow-y-auto">
        {/* 將 state 和 setter 傳遞下去，並指定 context 型別 */}
        <Outlet context={{ setBreadcrumbPaths, breadcrumbPaths } as OutletContext} />
      </main>
      <Footer />
    </div>
  );
}

export default Teacher;