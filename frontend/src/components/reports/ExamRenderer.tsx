import React from 'react';
import { MultipleChoiceQuestion } from './MultipleChoiceQuestion';
import { ShortAnswerQuestion } from './ShortAnswerQuestion';
import { TrueFalseQuestion } from './TrueFalseQuestion';

interface QuestionSource {
  page_number: string;
  evidence: string;
}

interface MultipleChoiceQuestionType {
  question_number: number;
  question_text: string;
  options: { [key: string]: string };
  correct_answer: string;
  source: QuestionSource;
}

interface ShortAnswerQuestionType {
  question_number: number;
  question_text: string;
  sample_answer: string;
  source: QuestionSource;
}

interface TrueFalseQuestionType {
  question_number: number;
  statement_text: string;
  correct_answer: 'True' | 'False';
  source: QuestionSource;
}

type Question = MultipleChoiceQuestionType | ShortAnswerQuestionType | TrueFalseQuestionType;

interface QuestionTypeBlock {
  type: 'multiple_choice' | 'short_answer' | 'true_false';
  questions: Question[];
}

interface ExamRendererProps {
  content: QuestionTypeBlock[];
}

const renderQuestionComponent = (type: string, question: Question) => {
  switch (type) {
    case 'multiple_choice':
      return <MultipleChoiceQuestion question={question as MultipleChoiceQuestionType} />;
    case 'short_answer':
      return <ShortAnswerQuestion question={question as ShortAnswerQuestionType} />;
    case 'true_false':
      return <TrueFalseQuestion question={question as TrueFalseQuestionType} />;
    default:
      return <p className="text-red-500">未知題型</p>;
  }
};

export const ExamRenderer: React.FC<ExamRendererProps> = ({ content }) => {
  let globalQuestionNumber = 0;
  
  if (!content || !Array.isArray(content)) {
    return <p className="text-red-500">測驗內容格式不正確。</p>;
  }

  return (
    <div className="exam-body space-y-6">
      {content.map((typeBlock, typeIndex) => {
        if (!typeBlock.questions || !Array.isArray(typeBlock.questions)) {
            return null; // Skip malformed type blocks
        }
        return (
          <div key={typeIndex} className="question-type-block border-t pt-4 first:border-t-0 first:pt-0">
            <h3 className="text-xl font-semibold text-gray-800 mb-3">
              {typeBlock.type === 'multiple_choice' ? '選擇題' : 
               typeBlock.type === 'short_answer' ? '簡答題' : 
               typeBlock.type === 'true_false' ? '是非題' : 
               '其他題型'}
            </h3>
            
            <div className="space-y-4">
              {typeBlock.questions.map((q, qIndex) => {
                globalQuestionNumber++;
                
                return (
                  <div key={qIndex} className="question-item p-4 bg-gray-50 rounded-md shadow-sm">
                    <p className="question-text text-gray-900 font-medium mb-2">
                      {globalQuestionNumber}. {q.question_text || (q as TrueFalseQuestionType).statement_text}
                    </p>
                    {renderQuestionComponent(typeBlock.type, q)}
                    <div className="source-info text-sm text-gray-500 mt-3 border-t pt-2">
                      <span className="source-page">P.{q.source.page_number}</span> | 
                      <span className="source-evidence">{q.source.evidence}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
};
