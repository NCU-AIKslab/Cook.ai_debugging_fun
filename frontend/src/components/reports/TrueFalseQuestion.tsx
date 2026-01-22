import React from 'react';

interface TrueFalseQuestionProps {
  question: {
    question_number: number;
    statement_text: string;
    correct_answer: 'True' | 'False';
    source: {
      page_number: string;
      evidence: string;
    };
  };
  showAnswer?: boolean;
}

export const TrueFalseQuestion: React.FC<TrueFalseQuestionProps> = ({ question, showAnswer }) => {
    const shouldShowAnswer = showAnswer !== false;
  return (
    <div className="true-false-block mt-2">
      {shouldShowAnswer && (
        <div className="answer-block">
          <p className="font-semibold text-gray-700">【答案】 
            <span className={question.correct_answer === 'True' ? 'text-green-600' : 'text-red-600'}>
              {question.correct_answer}
            </span>
          </p>
        </div>
      )}
    </div>
  );
};
