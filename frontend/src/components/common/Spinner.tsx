import React from 'react';

const Spinner: React.FC = () => {
  return (
    <div className="flex justify-center items-center h-full">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-theme-primary border-t-transparent"></div>
    </div>
  );
};

export default Spinner;
