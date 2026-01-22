import React from 'react';

interface MultipleChoiceQuestionProps {
  question: {
    question_number: number;
    question_text: string;
    options: { [key: string]: string };
    correct_answer: string;
    source: {
      page_number: string;
      evidence: string;
    };
  };
  showAnswer?: boolean;
}

export const MultipleChoiceQuestion: React.FC<MultipleChoiceQuestionProps> = ({ question, showAnswer = true}) => {
  return (
    <ul className="options-list mt-2 space-y-1 text-gray-700">
      {Object.entries(question.options).map(([key, value]) => (
        <li 
          key={key} 
          className={`px-2 py-1 rounded-md ${
            showAnswer && key === question.correct_answer 
              ? 'bg-green-100 text-green-800 font-medium' 
              : 'bg-white hover:bg-gray-50'
          }`}
        >
          <span className="font-semibold mr-1">{key}.</span> {value}
        </li>
      ))}
    </ul>
  );
};
