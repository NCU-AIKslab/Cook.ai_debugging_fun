
import React from 'react';

// ================= TYPES =================

export interface ArchitectureItem {
    intention: string;
    code: string;
}

export interface ArchitectureData {
    items: ArchitectureItem[];
}

export interface Option {
    id: number;
    label: string;
    feedback: string;
}

export interface QuestionContent {
    text: string;
    code: { content: string };
}

export interface AnswerConfig {
    correct_id: number;
    explanation: string;
}

export interface ExplanationQuestion {
    id: string; // e.g., Q1
    type: string;
    targeted_concept: string;
    options: Option[];
    question: QuestionContent;
    answer_config: AnswerConfig;
}

export interface DebuggingQuestion {
    id: string;
    type: string;
    targeted_concept: string;
    options: Option[];
    question: QuestionContent;
    answer_config: AnswerConfig;
}

// ================= COMPONENTS =================

// --- Architecture Editor ---
export const ArchitectureEditor: React.FC<{ data: any; onChange: (d: any) => void }> = ({ data, onChange }) => {
    // Determine initial values (handle legacy array format or new object format)
    const intention = data?.intention || (Array.isArray(data?.items) && data.items[0]?.intention) || '';
    const code = data?.code || (Array.isArray(data?.items) && data.items[0]?.code) || '';

    const updateField = (field: string, value: string) => {
        onChange({ ...data, [field]: value, items: undefined }); // Remove 'items' if upgrading from legacy
    };

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-gray-700">Architecture Template (Single)</h3>
            <div className="border p-4 rounded bg-gray-50">
                <div className="flex flex-col gap-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">Code Template</label>
                        <textarea
                            className="w-full border p-2 rounded h-96 font-mono text-sm"
                            value={code}
                            onChange={(e) => updateField('code', e.target.value)}
                            placeholder="# Put your code template here..."
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

// --- Explanation / Debugging Editor (Shared Structure) ---
// Both have similar structure: List of Questions with Options and Code.
// We can make a generic QuestionEditor or specific ones.
// Let's make one component that handles a list of questions.

const QuestionItemEditor: React.FC<{
    question: ExplanationQuestion | DebuggingQuestion;
    index: number;
    onChange: (q: ExplanationQuestion | DebuggingQuestion) => void;
    onRemove: () => void
}> = ({ question, index, onChange, onRemove }) => {

    const updateField = (field: string, value: any) => {
        onChange({ ...question, [field]: value });
    };

    const updateNested = (parent: string, field: string, value: any) => {
        // @ts-ignore
        onChange({ ...question, [parent]: { ...question[parent], [field]: value } });
    };

    const updateOption = (optIdx: number, field: keyof Option, value: any) => {
        const newOptions = [...question.options];
        newOptions[optIdx] = { ...newOptions[optIdx], [field]: value };
        onChange({ ...question, options: newOptions });
    };

    const addOption = () => {
        const newId = question.options.length + 1;
        onChange({ ...question, options: [...question.options, { id: newId, label: '', feedback: '' }] });
    };

    const removeOption = (optIdx: number) => {
        const removedOption = question.options[optIdx];
        const newOptions = [...question.options];
        newOptions.splice(optIdx, 1);
        // 重新編號 id
        const reindexed = newOptions.map((opt, i) => ({ ...opt, id: i + 1 }));

        // 調整 correct_id
        let newCorrectId = question.answer_config.correct_id;
        if (removedOption.id === newCorrectId) {
            // 被刪的是正確答案，重置為 1
            newCorrectId = reindexed.length > 0 ? 1 : 0;
        } else if (removedOption.id < newCorrectId) {
            // 正確答案在被刪選項之後，id 需要 -1
            newCorrectId = newCorrectId - 1;
        }

        onChange({
            ...question,
            options: reindexed,
            answer_config: { ...question.answer_config, correct_id: newCorrectId }
        });
    };

    // Code content path depends on type but structure provided is consistant: question.code.content
    // Wait, type definition:
    // Explanation: question: { text, code: { content } }
    // Debugging: question: { text, code: { content } }
    // Consistent!

    return (
        <div className="border p-4 rounded bg-gray-50 mb-4 relative">
            <button
                onClick={onRemove}
                className="absolute top-2 right-2 text-red-500 hover:text-red-700 font-bold"
            >
                ✕
            </button>
            <h4 className="font-medium mb-2 text-blue-600">Question {index + 1} ({question.id})</h4>

            <div className="grid grid-cols-1 gap-4 mb-4">
                <div>
                    <label className="block text-sm font-medium mb-1">Target Concept</label>
                    <input
                        className="w-full border p-2 rounded"
                        value={question.targeted_concept}
                        onChange={(e) => updateField('targeted_concept', e.target.value)}
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1">Question Text</label>
                    <textarea
                        className="w-full border p-2 rounded h-16"
                        value={question.question.text}
                        onChange={(e) => updateNested('question', 'text', e.target.value)}
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1">Code Snippet</label>
                    <textarea
                        className="w-full border p-2 rounded h-24 font-mono text-sm"
                        value={question.question.code.content}
                        onChange={(e) => {
                            // Deep update for question.code.content
                            const q = { ...question };
                            q.question = { ...q.question, code: { ...q.question.code, content: e.target.value } };
                            onChange(q);
                        }}
                    />
                </div>
            </div>

            <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Options</label>
                {question.options.map((opt, optIdx) => (
                    <div key={optIdx} className="flex gap-2 mb-2 items-start">
                        <span className="mt-2 text-sm font-bold text-gray-500 w-6">{opt.id}.</span>
                        <div className="flex-1 space-y-1">
                            <input
                                className="w-full border p-1 rounded text-sm"
                                placeholder="Label"
                                value={opt.label}
                                onChange={(e) => updateOption(optIdx, 'label', e.target.value)}
                            />
                            <input
                                className="w-full border p-1 rounded text-sm text-gray-600"
                                placeholder="Feedback"
                                value={opt.feedback}
                                onChange={(e) => updateOption(optIdx, 'feedback', e.target.value)}
                            />
                        </div>
                        <button onClick={() => removeOption(optIdx)} className="text-red-400 hover:text-red-600">×</button>
                    </div>
                ))}
                <button onClick={addOption} className="text-sm text-blue-600 hover:underline">+ Add Option</button>
            </div>

            <div className="grid grid-cols-2 gap-4 bg-blue-50 p-3 rounded">
                <div>
                    <label className="block text-sm font-medium mb-1">Correct Option ID</label>
                    <input
                        type="number"
                        className="w-full border p-2 rounded"
                        value={question.answer_config.correct_id}
                        onChange={(e) => updateNested('answer_config', 'correct_id', parseInt(e.target.value))}
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium mb-1">Explanation</label>
                    <textarea
                        className="w-full border p-2 rounded h-16 text-sm"
                        value={question.answer_config.explanation}
                        onChange={(e) => updateNested('answer_config', 'explanation', e.target.value)}
                    />
                </div>
            </div>
        </div>
    );
};

export const QuestionsListEditor: React.FC<{
    data: ExplanationQuestion[] | DebuggingQuestion[];
    type: 'explanation' | 'debugging';
    onChange: (d: any[]) => void
}> = ({ data, type, onChange }) => {

    const addQuestion = () => {
        const newQ: any = {
            id: `Q${(data || []).length + 1}`,
            type: type === 'explanation' ? 'code_explanation' : 'debugging',
            targeted_concept: '',
            options: [],
            question: { text: '', code: { content: '' } },
            answer_config: { correct_id: 1, explanation: '' }
        };
        onChange([...(data || []), newQ]);
    };

    const updateQuestion = (index: number, val: any) => {
        const newData = [...(data || [])];
        newData[index] = val;
        onChange(newData);
    };

    const removeQuestion = (index: number) => {
        const newData = [...(data || [])];
        newData.splice(index, 1);
        onChange(newData);
    };

    return (
        <div className="space-y-4">
            <h3 className="font-semibold text-gray-700 capitalize">{type} Questions</h3>
            {(Array.isArray(data) ? data : []).map((q, idx) => (
                <QuestionItemEditor
                    key={idx}
                    index={idx}
                    question={q as any}
                    onChange={(val) => updateQuestion(idx, val)}
                    onRemove={() => removeQuestion(idx)}
                />
            ))}
            <button onClick={addQuestion} className="w-full py-2 border-2 border-dashed border-gray-300 rounded text-gray-500 hover:border-gray-400 hover:text-gray-600">
                + Add Question
            </button>
        </div>
    );
}

