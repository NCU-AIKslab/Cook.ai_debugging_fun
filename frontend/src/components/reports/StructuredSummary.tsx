import React from 'react';

interface SummarySection {
  section_title: string;
  content_list: string[];
}

interface StructuredSummaryProps {
  content: SummarySection[]; // Corrected to directly receive array
}

export const StructuredSummary: React.FC<StructuredSummaryProps> = ({ content }) => {
  if (!content || !Array.isArray(content)) { // Corrected check
    return <p className="text-red-500">摘要內容格式不正確。</p>;
  }

  return (
    <div className="summary-body space-y-4">
      {content.map((section, index) => ( // Direct map over content
        <div key={index} className="summary-section p-3 bg-gray-50 rounded-md">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            {section.section_title}
          </h3>
          <ul className="list-disc list-inside text-gray-700">
            {section.content_list.map((point, pointIndex) => (
              <li key={pointIndex}>{point}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
};
