import React from 'react';
import { GeneralMessage } from './GeneralMessage';
import { StructuredSummary } from './StructuredSummary';
import { ExamRenderer } from './ExamRenderer';
import { FallbackMessage } from './FallbackMessage';

interface APIResult {
  job_id: number;
  display_type: 'text_message' | 'summary_report' | 'exam_questions' | string;
  title: string;
  content: any;
}

interface ReportContainerProps {
  result: APIResult;
}

const componentMap: { [key: string]: React.ComponentType<any> } = {
  text_message: GeneralMessage,
  summary_report: StructuredSummary,
  exam_questions: ExamRenderer,
};

export const ReportContainer: React.FC<ReportContainerProps> = ({ result }) => {
  if (!result || !result.display_type) {
    return <FallbackMessage content="無效的生成結果或類型不明" />;
  }
  
  const ContentComponent = componentMap[result.display_type] || FallbackMessage;

  return (
    <div className="report-card p-4 bg-white rounded-lg shadow-md mb-4">
      <div className="report-header mb-3">
        <h2 className="text-xl font-semibold text-gray-800">{result.title}</h2>
        {/* You can add auxiliary info here like job_id, status, time etc. */}
        {/* <p className="text-sm text-gray-500">Job ID: {result.job_id}</p> */}
      </div>
      
      <div className="report-content">
        <ContentComponent content={result.content} />
      </div>
    </div>
  );
};
