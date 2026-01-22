import React, { useState } from 'react';

interface ShortAnswerQuestionProps {
  question: {
    question_number: number;
    question_text: string;
    sample_answer: string;
    source: {
      page_number: string;
      evidence: string;
    };
  };
  showAnswer?: boolean;
}

export const ShortAnswerQuestion: React.FC<ShortAnswerQuestionProps> = ({ question, showAnswer }) => {
  const [isAnswerVisible, setIsAnswerVisible] = useState(false); 

  const handleToggleAnswer = () => {
      if (showAnswer !== undefined) return; 
      
      setIsAnswerVisible(prev => !prev);
  };
  
  const finalShowAnswer = showAnswer !== undefined ? showAnswer : isAnswerVisible;

  return (
    <div className="short-answer-block mt-2 cursor-pointer" onClick={handleToggleAnswer}> 
      <p className="text-sm text-gray-500 mb-1 select-none">
          {finalShowAnswer ? '【答案已顯示】點擊隱藏' : '【點擊顯示參考答案】'}
      </p>
    {finalShowAnswer && (
      <div className="answer-block bg-blue-50 p-3 rounded-md border-l-4 border-blue-200">
        <p className="font-semibold text-blue-800">【參考答案】</p>
        <div className="sample-answer text-blue-700 mt-1">
          {question.sample_answer}
        </div>
      </div>
    )}
  </div>  
  );
};