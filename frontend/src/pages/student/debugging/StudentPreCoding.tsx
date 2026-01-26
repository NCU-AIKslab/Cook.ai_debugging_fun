import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useUser } from '../../../contexts/UserContext';
import Sidebar from '../../../components/student/debugging/Sidebar';

const API_BASE_URL = "http://127.0.0.1:5000";

// --- 1. 介面定義 (對應後端資料結構) ---

interface Option {
    id: number;
    label: string;
}

interface QuestionBlock {
    code?: {
        content: string;
        language: string;
    };
    text: string;
}

interface Question {
    id: string;
    type: string;
    options: Option[];
    question: QuestionBlock;
}

interface StudentResponse {
    q_id: string;
    selected_option_id: number;
    is_correct: boolean;
}

interface PreCodingState {
    current_stage: 'logic' | 'error_code' | 'explain_code' | 'completed';
    is_completed: boolean;
    student_status: {
        logic: StudentResponse[];
        error_code: StudentResponse[];
        explain_code: StudentResponse[];
    };
    question_data: {
        logic_question: Question[];
        error_code_question: Question[];
        explain_code_question: Question[];
    };
    template?: any;
}

// 用於暫存提交後的回饋
interface FeedbackState {
    [questionId: string]: {
        feedback: string;
        explanation?: string;
    };
}

const PreCoding: React.FC = () => {
    const { user } = useUser();

    // 從 UserContext 獲取學生資訊
    const student = {
        stu_id: user?.user_id?.toString() || "113522096",
        name: user?.full_name || "Student"
    };

    // --- 狀態管理 ---
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [selectedProblemId, setSelectedProblemId] = useState<string | null>(null);
    const [problemData, setProblemData] = useState<any>(null);

    const [pcData, setPcData] = useState<PreCodingState | null>(null);
    const [pcLoading, setPcLoading] = useState(false);
    const [submittingIds, setSubmittingIds] = useState<Set<string>>(new Set());

    // 解析回饋狀態 (含 LocalStorage 讀取邏輯)
    const [feedbackMap, setFeedbackMap] = useState<FeedbackState>({});
    const [error, setError] = useState<string | null>(null);

    // --- 版面伸縮狀態 ---
    const [leftWidth, setLeftWidth] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // --- Helper: LocalStorage Key ---
    const getStorageKey = (pId: string) => `precoding_feedback_${student.stu_id}_${pId}`;

    // --- Helper: 處理 Template 顯示內容 (修正 JSON 顯示問題) ---
    const getTemplateContent = (tmpl: any) => {
        if (!tmpl) return "";
        if (typeof tmpl === 'string') return tmpl;
        if (tmpl.content) return tmpl.content;
        if (tmpl.code) return tmpl.code;
        return JSON.stringify(tmpl, null, 2);
    };

    // --- 拖拉處理邏輯 ---
    const startResizing = useCallback(() => setIsDragging(true), []);
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging || !containerRef.current) return;
            const containerRect = containerRef.current.getBoundingClientRect();
            let newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
            if (newWidth < 20) newWidth = 20;
            if (newWidth > 80) newWidth = 80;
            setLeftWidth(newWidth);
        };
        const handleMouseUp = () => setIsDragging(false);
        if (isDragging) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
        } else {
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        }
        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging]);

    // --- 資料抓取與初始化 ---
    useEffect(() => {
        const fetchData = async () => {
            if (!selectedProblemId) return;

            setError(null);
            setPcData(null);
            setProblemData(null);

            // 1. 嘗試從 LocalStorage 恢復該題目的解析紀錄
            try {
                const savedFeedback = localStorage.getItem(getStorageKey(selectedProblemId));
                if (savedFeedback) {
                    setFeedbackMap(JSON.parse(savedFeedback));
                } else {
                    setFeedbackMap({});
                }
            } catch (e) {
                console.error("Failed to load feedback from storage", e);
                setFeedbackMap({});
            }

            // 2. 載入左側題目描述
            try {
                const res = await axios.get(`${API_BASE_URL}/debugging/problems/${selectedProblemId}`);
                setProblemData(res.data);
            } catch (err) {
                console.warn("左側題目載入失敗", err);
            }

            // 3. 載入右側 Pre-Coding 狀態
            setPcLoading(true);
            try {
                const res = await axios.get(`${API_BASE_URL}/debugging/precoding/${selectedProblemId}`, {
                    params: { student_id: student.stu_id }
                });

                const rawData = res.data;
                if (!rawData || !rawData.question_data) {
                    throw new Error("後端回傳資料結構缺漏");
                }

                if (rawData.template && typeof rawData.template === 'string') {
                    try { rawData.template = JSON.parse(rawData.template); } catch { }
                }

                setPcData(rawData);
            } catch (err: any) {
                console.error("Fetch Error:", err);
                setError(err.response?.status === 404 ? "無題目：此單元尚未建立觀念引導" : `載入錯誤: ${err.message}`);
            } finally {
                setPcLoading(false);
            }
        };

        fetchData();
    }, [selectedProblemId, student.stu_id]);

    // --- 提交邏輯 ---
    const handleAnswerSubmit = async (stage: 'logic' | 'error_code' | 'explain_code', questionId: string, optionId: number) => {
        if (!pcData || !selectedProblemId) return;
        if (submittingIds.has(questionId)) return;

        setSubmittingIds(prev => new Set(prev).add(questionId));

        try {
            const res = await axios.post(`${API_BASE_URL}/debugging/precoding/submit`, {
                student_id: student.stu_id,
                problem_id: selectedProblemId,
                stage: stage,
                question_id: questionId,
                selected_option_id: optionId
            });

            const { is_correct, feedback, explanation, next_stage, stage_completed } = res.data;

            // 1. 更新 React State
            setPcData(prev => {
                if (!prev) return null;
                const currentResponses = [...prev.student_status[stage]];
                const existingIdx = currentResponses.findIndex(r => r.q_id === questionId);

                const newResponse: StudentResponse = {
                    q_id: questionId,
                    selected_option_id: optionId,
                    is_correct: is_correct
                };

                if (existingIdx >= 0) {
                    currentResponses[existingIdx] = newResponse;
                } else {
                    currentResponses.push(newResponse);
                }

                return {
                    ...prev,
                    current_stage: next_stage,
                    is_completed: next_stage === 'completed',
                    student_status: {
                        ...prev.student_status,
                        [stage]: currentResponses
                    }
                };
            });

            // 2. 更新並持久化 Feedback
            setFeedbackMap(prev => {
                const newMap = {
                    ...prev,
                    [questionId]: { feedback, explanation }
                };
                localStorage.setItem(getStorageKey(selectedProblemId), JSON.stringify(newMap));
                return newMap;
            });

            // 3. 若階段完成，重新抓取 (取得最新的 Template 等)
            if (stage_completed && next_stage === 'completed') {
                setTimeout(async () => {
                    const refreshRes = await axios.get(`${API_BASE_URL}/debugging/precoding/${selectedProblemId}`, {
                        params: { student_id: student.stu_id }
                    });
                    let newData = refreshRes.data;
                    if (newData.template && typeof newData.template === 'string') {
                        try { newData.template = JSON.parse(newData.template); } catch { }
                    }
                    setPcData(newData);
                }, 500);
            }

        } catch (error: any) {
            alert(error.response?.data?.detail || "提交失敗");
        } finally {
            setSubmittingIds(prev => {
                const next = new Set(prev);
                next.delete(questionId);
                return next;
            });
        }
    };

    const safeText = (text: any) => {
        if (typeof text === 'string') return text;
        if (typeof text === 'object') return JSON.stringify(text);
        return "";
    };

    // --- 單一題目卡片元件 ---
    const QuestionCard = ({
        question,
        stage
    }: {
        question: Question,
        stage: 'logic' | 'error_code' | 'explain_code'
    }) => {
        if (!pcData) return null;

        const response = pcData.student_status[stage].find(r => r.q_id === question.id);
        const feedbackData = feedbackMap[question.id];

        const isCorrect = response?.is_correct || false;
        const selectedId = response?.selected_option_id;
        const isSubmitting = submittingIds.has(question.id);

        const showFeedback = response !== undefined;

        return (
            <div className={`border rounded-xl p-5 mb-6 transition-all duration-300 ${isCorrect
                ? 'bg-green-50 border-green-200 shadow-sm'
                : (selectedId !== undefined)
                    ? 'bg-white border-red-200 shadow-sm'
                    : 'bg-white border-gray-200 shadow-sm hover:shadow-md'
                }`}>
                {/* 標題與狀態 */}
                <div className="flex items-center justify-between mb-3">
                    <h3 className={`font-bold text-md ${isCorrect ? 'text-green-800' : 'text-gray-800'}`}>
                        {question.id}
                    </h3>
                    {isCorrect && <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-bold">Passed ✅</span>}
                    {!isCorrect && selectedId !== undefined && <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-bold">Try Again ⚠️</span>}
                </div>

                {/* 題目內容 */}
                <div className="mb-4">
                    <div className="text-gray-800 font-medium whitespace-pre-wrap mb-2">
                        {safeText(question.question.text)}
                    </div>
                    {question.question.code && (
                        <div className="bg-gray-800 text-gray-100 p-3 rounded-md text-sm font-mono overflow-x-auto">
                            <pre className="whitespace-pre">{question.question.code.content}</pre>
                        </div>
                    )}
                </div>

                {/* 選項列表 */}
                <div className="space-y-2">
                    {question.options.map((opt) => {
                        const isSelected = selectedId === opt.id;
                        let btnClass = "w-full text-left p-3 rounded-lg border transition-all duration-200 flex items-center text-sm ";

                        if (isCorrect) {
                            if (isSelected) btnClass += "bg-green-600 text-white border-green-600 font-medium";
                            else btnClass += "bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed opacity-50";
                        } else if (isSelected) {
                            btnClass += "bg-red-500 text-white border-red-500";
                        } else {
                            btnClass += "hover:bg-blue-50 hover:border-blue-300 bg-white border-gray-200 text-gray-700 hover:shadow-sm";
                        }

                        return (
                            <button
                                key={opt.id}
                                disabled={isCorrect || isSubmitting}
                                onClick={() => handleAnswerSubmit(stage, question.id, opt.id)}
                                className={btnClass}
                            >
                                <div className={`w-5 h-5 rounded-full border flex items-center justify-center mr-3 text-xs shrink-0 ${isCorrect && isSelected ? 'bg-white text-green-600 border-white' :
                                    isSelected && !isCorrect ? 'bg-white text-red-500 border-white' :
                                        'border-gray-400 text-gray-500'
                                    }`}>
                                    {isSubmitting && isSelected ? '...' : String.fromCharCode(64 + opt.id)}
                                </div>
                                <span>{opt.label}</span>
                            </button>
                        );
                    })}
                </div>

                {/* 回饋區域 */}
                {showFeedback && (
                    <div className={`mt-4 p-3 rounded-lg border flex gap-3 animate-fade-in ${isCorrect ? 'bg-green-100 border-green-200 text-green-900' : 'bg-red-50 border-red-200 text-red-900'
                        }`}>
                        <div className="text-lg shrink-0">
                            {isCorrect ? '💡' : '🧐'}
                        </div>
                        <div>
                            <p className="font-bold text-xs mb-1">
                                回饋 (Feedback)
                            </p>
                            <p className="text-xs opacity-90 leading-relaxed">
                                {feedbackData?.feedback || (isCorrect ? "作答正確！" : "答案錯誤，請參考題目提示。")}
                            </p>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // --- 共用的鎖定訊息元件 ---
    const LockedSection = () => (
        <div className="border border-gray-200 rounded-xl p-8 bg-gray-50 opacity-70 text-center border-dashed mb-6 select-none flex flex-col items-center justify-center h-32">
            <div className="text-3xl mb-3">🔒</div>
            <p className="text-sm text-gray-500 font-medium">請先完成上一階段以解鎖。</p>
        </div>
    );

    // --- 主介面渲染 (修正版排版) ---
    return (
        // 使用 Flex Row 確保左右不重疊
        <div className="flex h-full w-full bg-white">

            {/* Sidebar (直接使用元件，透過 isOpen 控制內部顯示) */}
            <Sidebar
                isOpen={isSidebarOpen}
                selectedProblemId={selectedProblemId}
                onSelectProblem={setSelectedProblemId}
            />

            {/* Main Content */}
            {/* flex-1 讓內容佔滿剩餘空間，min-w-0 防止內容撐開 */}
            <div className="flex-1 flex flex-col h-full min-w-0 bg-white">

                {/* Header (樣式同步 StudentCodingHelp) */}
                <div className="h-12 border-b border-gray-200 flex items-center px-4 bg-white shrink-0 justify-between">
                    <div className="flex items-center">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="mr-3 text-gray-500 hover:text-gray-700 focus:outline-none"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                        </button>
                        <h2 className="font-bold text-gray-800">{problemData?.title || '請選擇題目'}</h2>
                    </div>
                </div>

                {/* Resizable Split Panes */}
                <div ref={containerRef} className="flex flex-1 overflow-hidden relative">

                    {/* Left Pane (題目資訊) */}
                    <div
                        className="flex flex-col border-r border-gray-200 h-full overflow-hidden bg-white"
                        style={{ width: `${leftWidth}%` }}
                    >
                        <div className="flex-1 overflow-y-auto p-6">
                            {problemData ? (
                                <>
                                    <div className="text-gray-600 mb-6 leading-relaxed whitespace-pre-wrap prose max-w-none" dangerouslySetInnerHTML={{ __html: problemData.description }} />

                                    <div className="mb-6 grid grid-cols-1 gap-4">
                                        <div>
                                            <h4 className="text-base font-bold text-gray-700 mb-1">輸入說明</h4>
                                            <div className="text-gray-600 text-base" dangerouslySetInnerHTML={{ __html: problemData.input_description }} />
                                        </div>
                                        <div>
                                            <h4 className="text-base font-bold text-gray-700 mb-1">輸出說明</h4>
                                            <div className="text-gray-600 text-base" dangerouslySetInnerHTML={{ __html: problemData.output_description }} />
                                        </div>
                                    </div>

                                    <div className="space-y-6">
                                        {problemData.samples && problemData.samples.length > 0 ? (
                                            problemData.samples.map((sample: any, index: number) => (
                                                <div key={index} className="bg-gray-50 p-3 rounded border border-gray-200">
                                                    <span className="text-xs font-bold text-gray-500 uppercase block mb-2 border-b border-gray-200 pb-1">Sample {index + 1}</span>
                                                    <div className="space-y-3 font-mono text-sm">
                                                        <div>
                                                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-1">Input</span>
                                                            <div className="bg-white p-2 rounded border border-gray-200 whitespace-pre-wrap">{sample.input}</div>
                                                        </div>
                                                        <div>
                                                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-1">Output</span>
                                                            <div className="bg-white p-2 rounded border border-gray-200 whitespace-pre-wrap">{sample.output}</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-gray-400 text-sm italic">無範例資料</div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="text-gray-400 mt-20 text-center">請從左側列表選擇一個題目</div>
                            )}
                        </div>
                    </div>

                    {/* Resizer */}
                    <div
                        className="w-1 bg-gray-200 hover:bg-blue-400 cursor-col-resize flex items-center justify-center transition-colors z-10"
                        onMouseDown={startResizing}
                    >
                        <div className="w-1 h-8 bg-gray-400 rounded-full"></div>
                    </div>

                    {/* Right Pane: Pre-Coding System */}
                    <div
                        className="flex flex-col bg-gray-50 h-full overflow-hidden"
                        style={{ width: `${100 - leftWidth}%` }}
                    >
                        <div className="px-6 py-4 bg-white border-b border-gray-200 shrink-0 shadow-sm">
                            <h2 className="text-lg font-bold text-gray-800 flex items-center">
                                <span className="text-blue-600 mr-2">✦ 觀念建構 (Pre-Coding)</span>
                            </h2>
                            <p className="text-xs text-gray-500 mt-1">
                                {pcData ? `進度：${pcData.current_stage === 'completed' ? '已完成' :
                                    pcData.current_stage === 'error_code' ? '第三階段' :
                                        pcData.current_stage === 'explain_code' ? '第二階段' :
                                            '第一階段'
                                    }` : '載入中...'}
                            </p>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
                            {/* Render Logic */}
                            {!selectedProblemId ? (
                                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                                    <p>請先選擇題目...</p>
                                </div>
                            ) : pcLoading ? (
                                <div className="flex justify-center items-center h-full text-gray-500 gap-2">
                                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                                    載入中...
                                </div>
                            ) : error ? (
                                <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2 px-6 text-center">
                                    <div className="text-3xl opacity-50">📂</div>
                                    <p className="font-medium text-red-500">{error}</p>
                                </div>
                            ) : pcData ? (
                                <div className="max-w-3xl mx-auto pb-10">

                                    {/* 1. 邏輯思考區塊 (永遠開啟) */}
                                    <div className="mb-8">
                                        <h2 className="text-lg font-bold text-blue-700 mb-4 flex items-center">
                                            <span className="bg-blue-100 text-blue-600 w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2">1</span>
                                            邏輯思考 (Logic)
                                        </h2>
                                        {/* 邏輯題總是顯示 */}
                                        {pcData.question_data.logic_question.map(q => (
                                            <QuestionCard key={q.id} question={q} stage="logic" />
                                        ))}
                                    </div>

                                    {/* 2. 程式碼解釋區塊 (新) */}
                                    <div className="mb-8">
                                        <h2 className={`text-lg font-bold mb-4 flex items-center ${pcData.current_stage === 'logic' ? 'text-gray-400' : 'text-orange-700'}`}>
                                            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2 ${pcData.current_stage === 'logic' ? 'bg-gray-200' : 'bg-orange-100 text-orange-600'}`}>2</span>
                                            程式碼解釋 (Code Explanation)
                                        </h2>

                                        {/* 鎖定邏輯：如果還在 logic 階段，顯示鎖頭 */}
                                        {pcData.current_stage === 'logic' ? (
                                            <LockedSection />
                                        ) : (
                                            pcData.question_data.explain_code_question.map(q => (
                                                <QuestionCard key={q.id} question={q} stage="explain_code" />
                                            ))
                                        )}
                                    </div>
                                    {/* 3. 程式除錯區塊 */}
                                    <div className="mb-8">
                                        <h2 className={`text-lg font-bold mb-4 flex items-center ${['logic', 'explain_code'].includes(pcData.current_stage) ? 'text-gray-400' : 'text-purple-700'}`}>
                                            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2 ${['logic', 'explain_code'].includes(pcData.current_stage) ? 'bg-gray-200' : 'bg-purple-100 text-purple-600'}`}>3</span>
                                            程式除錯 (Debugging)
                                        </h2>

                                        {/* 鎖定邏輯：如果還在 logic 或 explain_code 階段，顯示鎖頭 */}
                                        {['logic', 'explain_code'].includes(pcData.current_stage) ? (
                                            <LockedSection />
                                        ) : (
                                            pcData.question_data.error_code_question.map(q => (
                                                <QuestionCard key={q.id} question={q} stage="error_code" />
                                            ))
                                        )}
                                    </div>


                                    {/* 4. 程式碼架構區塊 (Template) */}
                                    <div className="mb-8">
                                        <h2 className={`text-lg font-bold mb-4 flex items-center ${!pcData.is_completed ? 'text-gray-400' : 'text-gray-700'}`}>
                                            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2 ${!pcData.is_completed ? 'bg-gray-200' : 'bg-gray-200 text-gray-600'}`}>4</span>
                                            程式碼架構 (Template)
                                        </h2>

                                        {/* 鎖定邏輯：如果未完成，顯示鎖頭 */}
                                        {!pcData.is_completed ? (
                                            <LockedSection />
                                        ) : (
                                            <div className="animate-fade-in-up">
                                                <div className="border border-gray-300 rounded-xl overflow-hidden shadow-sm">
                                                    <div className="bg-gray-100 px-4 py-2 border-b border-gray-300 flex justify-between items-center">
                                                        <span className="font-bold text-gray-700 text-sm">📄 Template Code</span>
                                                        {/* <button
                                                            onClick={() => navigator.clipboard.writeText(getTemplateContent(pcData.template))}
                                                            className="text-xs text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                                                        >
                                                            複製
                                                        </button> */}
                                                    </div>
                                                    {/* 使用 whitespace-pre 搭配 overflow-auto 實現橫向捲軸 */}
                                                    <pre className="bg-[#1e1e1e] text-gray-100 p-4 text-sm font-mono overflow-auto max-h-[500px] leading-relaxed whitespace-pre">
                                                        {getTemplateContent(pcData.template)}
                                                    </pre>
                                                </div>

                                                {/* 完成訊息移至最底部 */}
                                                <div className="mt-6 flex justify-center items-center p-4 bg-green-50 border border-green-200 rounded-xl text-green-700">
                                                    <span className="text-xl mr-2">🎉</span>
                                                    <span className="font-bold">觀念建構已完成！您可以開始撰寫程式了。</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                </div>
                            ) : null}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PreCoding;