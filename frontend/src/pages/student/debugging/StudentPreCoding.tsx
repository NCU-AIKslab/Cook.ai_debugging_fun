import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useUser } from '../../../contexts/UserContext'; // 假設路徑正確
import Sidebar from '../../../components/student/debugging/Sidebar'; // 假設路徑正確
import API_BASE_URL from '../../../config/api';

// --- 1. 介面定義 ---

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

// 對話紀錄介面
interface ChatMessage {
    role: 'agent' | 'student';
    content: string;
    stage: string;
    score: number;
    timestamp: string;
}

// Logic 對話狀態
interface LogicChatState {
    status: 'new' | 'existing';
    current_stage: 'UNDERSTANDING' | 'DECOMPOSITION' | 'COMPLETED';
    current_score: number;
    is_completed: boolean;
    chat_log: ChatMessage[];
    suggested_replies?: string[];
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

interface FeedbackState {
    [questionId: string]: {
        feedback: string;
        explanation?: string;
    };
}

// 新增 Props 定義以配合 StudentCoding.tsx
interface PreCodingProps {
    student?: {
        stu_id: string;
        name: string;
    };
}

const PreCoding: React.FC<PreCodingProps> = ({ student: propStudent }) => {
    const { user } = useUser();

    // 優先使用 props 傳入的 student，如果沒有則使用 UserContext，最後 fallback
    const student = propStudent || {
        stu_id: user?.user_id?.toString() || "113522096",
        name: user?.full_name || "Student"
    };

    // --- 狀態管理 ---
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [selectedProblemId, setSelectedProblemId] = useState<string | null>(null);
    const [problemData, setProblemData] = useState<any>(null);

    // Tab 狀態
    const [activeTab, setActiveTab] = useState<'concept' | 'implementation'>('concept');

    // Time Status Logic
    const [timeStatus, setTimeStatus] = useState<'active' | 'not_started' | 'ended'>('active');

    useEffect(() => {
        const checkTimeStatus = () => {
            if (!problemData) return;
            const now = new Date();

            if (problemData.start_time) {
                const start = new Date(problemData.start_time);
                if (now < start) {
                    setTimeStatus('not_started');
                    return;
                }
            }

            if (problemData.end_time) {
                const end = new Date(problemData.end_time);
                if (now > end) {
                    setTimeStatus('ended');
                    return;
                }
            }

            setTimeStatus('active');
        };

        checkTimeStatus();
        const interval = setInterval(checkTimeStatus, 1000); // Check every second for immediate active/lock update
        return () => clearInterval(interval);
    }, [problemData]);

    // 舊版 Pre-Coding 狀態
    const [pcData, setPcData] = useState<PreCodingState | null>(null);
    const [pcLoading, setPcLoading] = useState(false);
    const [submittingIds, setSubmittingIds] = useState<Set<string>>(new Set());

    // Logic Chat 狀態
    const [logicChatState, setLogicChatState] = useState<LogicChatState | null>(null);
    const [chatInput, setChatInput] = useState('');
    const [isSendingChat, setIsSendingChat] = useState(false);
    const [suggestedReplies, setSuggestedReplies] = useState<string[]>([]);
    const chatContainerRef = useRef<HTMLDivElement>(null);

    // IME 狀態 (中文輸入法)
    const [isComposing, setIsComposing] = useState(false);

    const [feedbackMap, setFeedbackMap] = useState<FeedbackState>({});
    const [error, setError] = useState<string | null>(null);

    // 版面伸縮狀態
    const [leftWidth, setLeftWidth] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // --- Helper Functions ---
    const getStorageKey = (pId: string) => `precoding_feedback_${student.stu_id}_${pId}`;

    const getTemplateContent = (tmpl: any) => {
        if (!tmpl) return "";
        if (typeof tmpl === 'string') return tmpl;
        if (tmpl.content) return tmpl.content;
        if (tmpl.code) return tmpl.code;
        return JSON.stringify(tmpl, null, 2);
    };

    const isLogicCompleted = logicChatState?.is_completed || false;

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

    // 自動滾動到底部
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [logicChatState?.chat_log]);

    // --- 資料抓取與初始化 ---
    useEffect(() => {
        const fetchData = async () => {
            if (!selectedProblemId) return;

            setError(null);
            setPcData(null);
            setProblemData(null);
            setLogicChatState(null);
            setSuggestedReplies([]);
            setActiveTab('concept');

            // 1. 嘗試從 LocalStorage 恢復回饋紀錄
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

            // 2. 載入題目資訊
            try {
                const res = await axios.get(`${API_BASE_URL}/debugging/problems/${selectedProblemId}`);
                setProblemData(res.data);
            } catch (err) {
                console.warn("左側題目載入失敗", err);
            }

            // 3. 載入 Logic Chat 狀態
            setPcLoading(true);
            try {
                const logicRes = await axios.get(`${API_BASE_URL}/debugging/precoding/logic/status/${selectedProblemId}`, {
                    params: { student_id: student.stu_id }
                });

                if (logicRes.data.status === 'success') {
                    const data = logicRes.data.data;
                    setLogicChatState(data);
                    // 新增：從 API 回傳中初始化建議回覆
                    if (data.suggested_replies && data.suggested_replies.length > 0) {
                        setSuggestedReplies(data.suggested_replies);
                    }
                    if (data.is_completed) {
                        setActiveTab('implementation');
                    }
                }
            } catch (err) {
                console.warn("Logic Chat 載入失敗", err);
            }

            // 4. 載入舊版 Pre-Coding 狀態
            try {
                const res = await axios.get(`${API_BASE_URL}/debugging/precoding/${selectedProblemId}`, {
                    params: { student_id: student.stu_id }
                });

                const rawData = res.data;
                if (!rawData || !rawData.question_data) {
                    // throw new Error("後端回傳資料結構缺漏"); 
                    // 容錯處理：若無舊版資料，可能只是純對話題
                }

                if (rawData.template && typeof rawData.template === 'string') {
                    try { rawData.template = JSON.parse(rawData.template); } catch { }
                }
                setPcData(rawData);
            } catch (err: any) {
                console.error("Fetch Error:", err);
                // 不一定報錯，可能只有 Logic Chat
            } finally {
                setPcLoading(false);
            }
        };

        fetchData();
    }, [selectedProblemId, student.stu_id]);

    // --- Chat 送出邏輯 ---
    const handleSendChat = async (messageOverride?: string) => {
        const userMessage = messageOverride || chatInput.trim();
        if (!userMessage || isSendingChat || !selectedProblemId || timeStatus !== 'active') return;

        setChatInput('');
        setSuggestedReplies([]);
        setIsSendingChat(true);

        // Optimistic UI update
        setLogicChatState(prev => {
            if (!prev) return prev;
            return {
                ...prev,
                chat_log: [
                    ...prev.chat_log,
                    {
                        role: 'student' as const,
                        content: userMessage,
                        stage: prev.current_stage,
                        score: prev.current_score,
                        timestamp: new Date().toISOString()
                    }
                ]
            };
        });

        try {
            const res = await axios.post(`${API_BASE_URL}/debugging/precoding/logic/chat`, {
                student_id: student.stu_id,
                problem_id: selectedProblemId,
                message: userMessage
            });

            if (res.data.status === 'success') {
                const data = res.data.data;
                setLogicChatState({
                    status: 'existing',
                    current_stage: data.current_stage,
                    current_score: data.current_score,
                    is_completed: data.is_completed,
                    chat_log: data.chat_log
                });

                if (data.suggested_replies && data.suggested_replies.length > 0) {
                    setSuggestedReplies(data.suggested_replies);
                } else {
                    setSuggestedReplies([]);
                }

                if (data.is_completed && pcData) {
                    setPcData(prev => {
                        if (!prev) return prev;
                        return {
                            ...prev,
                            current_stage: 'explain_code'
                        };
                    });
                }
            }
        } catch (err) {
            console.error("Chat Error:", err);
            setLogicChatState(prev => {
                if (!prev) return prev;
                return {
                    ...prev,
                    chat_log: prev.chat_log.slice(0, -1)
                };
            });
        } finally {
            setIsSendingChat(false);
        }
    };

    // 鍵盤事件處理
    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (isComposing) return; // 關鍵修正：IME 輸入中直接返回，不觸發 Enter

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendChat();
        }
    };

    // --- 舊版提交邏輯 ---
    const handleAnswerSubmit = async (stage: 'logic' | 'error_code' | 'explain_code', questionId: string, optionId: number) => {
        if (!pcData || !selectedProblemId || timeStatus !== 'active') return;
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

            setFeedbackMap(prev => {
                const newMap = {
                    ...prev,
                    [questionId]: { feedback, explanation }
                };
                localStorage.setItem(getStorageKey(selectedProblemId), JSON.stringify(newMap));
                return newMap;
            });

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

    // --- 原本的 ChatInterface 元件 (已移除 wrapper，直接在下方渲染) ---

    // --- 舊版題目卡片元件 ---
    const QuestionCard = ({
        question,
        stage
    }: {
        question: Question,
        stage: 'logic' | 'error_code' | 'explain_code'
    }) => {
        if (!pcData) return null;

        // 取得所有該題的作答紀錄
        const allResponses = pcData.student_status[stage].filter(r => r.q_id === question.id);
        // 最新的作答 (最終狀態)
        const latestResponse = allResponses[allResponses.length - 1];
        const feedbackData = feedbackMap[question.id];

        const isCorrect = latestResponse?.is_correct || false;
        const selectedId = latestResponse?.selected_option_id;
        const isSubmitting = submittingIds.has(question.id);

        const showFeedback = latestResponse !== undefined;

        // 完成後找出正確答案的選項 ID (從 is_correct=true 的紀錄中取得)
        const correctAnswerId = allResponses.find(r => r.is_correct)?.selected_option_id;

        return (
            <div className={`border rounded-xl p-5 mb-6 transition-all duration-300 ${isCorrect
                ? 'bg-green-50 border-green-200 shadow-sm'
                : (selectedId !== undefined)
                    ? 'bg-white border-red-200 shadow-sm'
                    : 'bg-white border-gray-200 shadow-sm hover:shadow-md'
                }`}>
                <div className="flex items-center justify-between mb-3">
                    <h3 className={`font-bold text-md ${isCorrect ? 'text-green-800' : 'text-gray-800'}`}>
                        {question.id}
                    </h3>
                    {isCorrect && <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-bold">Passed ✅</span>}
                    {!isCorrect && selectedId !== undefined && <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-bold">Try Again ⚠️</span>}
                </div>

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

                <div className="space-y-2">
                    {question.options.map((opt) => {
                        const isSelected = selectedId === opt.id;
                        const isLocked = pcData.is_completed || isCorrect;
                        const isCorrectOption = correctAnswerId === opt.id; // 這是正確答案選項
                        let btnClass = "w-full text-left p-3 rounded-lg border transition-all duration-200 flex items-center text-sm ";

                        if (isLocked) {
                            // 完成後狀態：正確答案選項顯示綠色，用戶選錯的顯示紅色
                            if (isCorrectOption) {
                                btnClass += "bg-green-600 text-white border-green-600 font-medium";
                            } else if (isSelected && !isCorrect) {
                                // 用戶選了但不是正確答案
                                btnClass += "bg-red-300 text-white border-red-300 font-medium";
                            } else {
                                btnClass += "bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed opacity-50";
                            }
                        } else if (isSelected) {
                            btnClass += "bg-red-500 text-white border-red-500";
                        } else {
                            btnClass += "hover:bg-blue-50 hover:border-blue-300 bg-white border-gray-200 text-gray-700 hover:shadow-sm";
                        }

                        return (
                            <button
                                key={opt.id}
                                disabled={isLocked || isSubmitting || timeStatus !== 'active'}
                                onClick={() => handleAnswerSubmit(stage, question.id, opt.id)}
                                className={btnClass}
                            >
                                <div className={`w-5 h-5 rounded-full border flex items-center justify-center mr-3 text-xs shrink-0 ${isLocked && isCorrectOption ? 'bg-white text-green-600 border-white' :
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

    // --- 鎖定區塊元件 ---
    const LockedSection = () => (
        <div className="border border-gray-200 rounded-xl p-8 bg-gray-50 opacity-70 text-center border-dashed mb-6 select-none flex flex-col items-center justify-center h-32">
            <div className="text-3xl mb-3">🔒</div>
            <p className="text-sm text-gray-500 font-medium">請先完成上一階段以解鎖。</p>
        </div>
    );

    // --- 主介面渲染 ---
    return (
        <div className="flex h-[calc(100vh-60px)] w-full bg-white">

            <Sidebar
                isOpen={isSidebarOpen}
                selectedProblemId={selectedProblemId}
                onSelectProblem={setSelectedProblemId}
            />

            <div className="flex-1 flex flex-col h-full min-w-0 bg-white">

                <div className="h-12 border-b border-gray-200 flex items-center px-4 bg-white shrink-0 justify-between">
                    <div className="flex items-center">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="mr-3 text-gray-500 hover:text-gray-700 focus:outline-none"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                        </button>
                        <h2 className="font-bold text-gray-800 flex items-center gap-2">
                            {problemData?.title || '請選擇題目'}
                            {timeStatus === 'ended' && <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded border border-red-200">考試結束 (Time's Up)</span>}
                            {timeStatus === 'not_started' && <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded border border-yellow-200">未開始 (Not Started)</span>}
                        </h2>
                    </div>
                </div>

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

                    {/* Right Pane: Pre-Coding System with Tabs */}
                    <div
                        className="flex flex-col bg-gray-50 h-full overflow-hidden"
                        style={{ width: `${100 - leftWidth}%` }}
                    >
                        {/* Tab Header */}
                        <div className="flex bg-white border-b border-gray-200">
                            <button
                                onClick={() => setActiveTab('concept')}
                                disabled={!selectedProblemId}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center gap-2
                                    ${!selectedProblemId
                                        ? 'border-transparent text-gray-300 cursor-not-allowed'
                                        : activeTab === 'concept'
                                            ? 'border-blue-500 text-blue-600'
                                            : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                <span>觀念建構</span>
                                {isLogicCompleted && <span className="flex items-center justify-center w-4 h-4 rounded-full bg-green-500 text-white text-[10px]">✓</span>}
                            </button>

                            <button
                                onClick={() => isLogicCompleted && setActiveTab('implementation')}
                                disabled={!selectedProblemId || !isLogicCompleted}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center gap-2
                                    ${!selectedProblemId || !isLogicCompleted
                                        ? 'border-transparent text-gray-300 cursor-not-allowed'
                                        : activeTab === 'implementation'
                                            ? 'border-green-500 text-green-700'
                                            : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                <span>實作引導</span>
                            </button>
                        </div>

                        <div className={`flex-1 overflow-y-auto scroll-smooth ${activeTab === 'concept' ? '' : 'p-6'}`}>
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
                            ) : (
                                <>
                                    {/* Tab 1: 觀念建構 - 滿版對話 */}
                                    {activeTab === 'concept' && (
                                        <div className="flex flex-col h-full">
                                            {logicChatState ? (
                                                <div className="flex flex-col h-full bg-white overflow-hidden">
                                                    {/* Stage Indicator 階段指標 + 得分點點 */}
                                                    {!logicChatState.is_completed && (
                                                        <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-gray-100">
                                                            {/* 階段標籤 */}
                                                            <div className="flex items-center gap-2">
                                                                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${logicChatState.current_stage === 'UNDERSTANDING'
                                                                    ? 'bg-blue-500 text-white shadow-sm'
                                                                    : 'bg-green-100 text-green-700'
                                                                    }`}>
                                                                    <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80"></span>
                                                                    理解問題
                                                                </div>
                                                                <div className="w-4 h-0.5 bg-gray-300 rounded-full"></div>
                                                                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all ${logicChatState.current_stage === 'DECOMPOSITION'
                                                                    ? 'bg-blue-500 text-white shadow-sm'
                                                                    : 'bg-gray-100 text-gray-400'
                                                                    }`}>
                                                                    <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80"></span>
                                                                    拆解問題
                                                                </div>
                                                            </div>
                                                            {/* 進度點點 (1-4 分) */}
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-xs text-gray-500 mr-1">進度:</span>
                                                                {[1, 2, 3, 4].map((dot) => (
                                                                    <div
                                                                        key={dot}
                                                                        className={`w-2.5 h-2.5 rounded-full transition-all ${dot <= logicChatState.current_score
                                                                            ? 'bg-blue-500'
                                                                            : 'bg-gray-200'
                                                                            }`}
                                                                    />
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                    {/* Chat Messages */}
                                                    <div
                                                        ref={chatContainerRef}
                                                        className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50"
                                                    >
                                                        {logicChatState.chat_log.map((msg, idx) => (
                                                            <div
                                                                key={idx}
                                                                className={`flex ${msg.role === 'student' ? 'justify-end' : 'justify-start'}`}
                                                            >
                                                                <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${msg.role === 'student'
                                                                    ? 'bg-blue-500 text-white rounded-br-md'
                                                                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md shadow-sm'
                                                                    }`}>
                                                                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                                                                </div>
                                                            </div>
                                                        ))}
                                                        {isSendingChat && (
                                                            <div className="flex justify-start">
                                                                <div className="bg-white border border-gray-200 rounded-2xl px-4 py-2.5 rounded-bl-md shadow-sm">
                                                                    <div className="flex gap-1">
                                                                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                                                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                                                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Suggested Replies + Input Area */}
                                                    {!logicChatState.is_completed ? (
                                                        <div className="border-t border-gray-200 bg-white">
                                                            {/* Suggested Replies 提示選項 */}
                                                            {suggestedReplies.length > 0 && (
                                                                <div className="px-4 pt-3 flex flex-wrap gap-2">
                                                                    {suggestedReplies.map((reply, idx) => (
                                                                        <button
                                                                            key={idx}
                                                                            // 修改: 點擊後累加到輸入框，不覆蓋
                                                                            onClick={() => setChatInput(prev => prev ? `${prev} ${reply}` : reply)}
                                                                            disabled={isSendingChat}
                                                                            className="px-3 py-1.5 text-sm bg-blue-50 text-blue-700 border border-blue-200 rounded-full hover:bg-blue-100 hover:border-blue-300 transition-colors disabled:opacity-50"
                                                                        >
                                                                            {reply}
                                                                        </button>
                                                                    ))}
                                                                </div>
                                                            )}
                                                            {/* Input Area */}
                                                            <div className="p-4 flex gap-2">
                                                                <textarea
                                                                    value={chatInput}
                                                                    onChange={(e) => setChatInput(e.target.value)}
                                                                    onKeyDown={handleKeyDown}
                                                                    onCompositionStart={() => setIsComposing(true)}
                                                                    onCompositionEnd={() => {
                                                                        setIsComposing(false);
                                                                    }}
                                                                    placeholder={timeStatus === 'not_started' ? "考試尚未開始。" : timeStatus === 'ended' ? "考試時間已結束。" : "輸入您的回答..."}
                                                                    className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 transition-all disabled:bg-gray-100 disabled:cursor-not-allowed"
                                                                    rows={2}
                                                                    disabled={isSendingChat || timeStatus !== 'active'}
                                                                />
                                                                <button
                                                                    onClick={() => handleSendChat()}
                                                                    disabled={!chatInput.trim() || isSendingChat || timeStatus !== 'active'}
                                                                    // 修改 2: 
                                                                    // - 移除 'self-end' (讓高度跟隨 flex 容器撐開，即與 textarea 等高)
                                                                    // - 加入 'h-auto flex items-center justify-center' (確保高度自動適應且文字置中)
                                                                    className="px-4 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium text-sm h-auto flex items-center justify-center"
                                                                >
                                                                    {timeStatus === 'active' ? 'Send' : 'Locked'}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <div className="p-4 border-t border-gray-200 bg-green-50">
                                                            <div className="flex items-center justify-center gap-2 text-green-700">
                                                                <span className="font-bold">觀念建構已完成！請切換至「實作引導」分頁。</span>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            ) : (
                                                <div className="flex-1 flex items-center justify-center">
                                                    <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200 text-yellow-700">
                                                        <p>正在載入對話介面...</p>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Tab 2: 實作引導 */}
                                    {activeTab === 'implementation' && pcData && (
                                        <div className="max-w-3xl mx-auto pb-10">
                                            {/* 程式碼解釋區塊 */}
                                            <div className="mb-8">
                                                <h2 className="text-lg font-bold text-gray-700 mb-4 flex items-center">
                                                    <span className="bg-gray-200 text-gray-600 w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2">1</span>
                                                    程式碼解釋 (Code Explanation)
                                                </h2>
                                                {pcData.question_data.explain_code_question.map(q => (
                                                    <QuestionCard key={q.id} question={q} stage="explain_code" />
                                                ))}
                                            </div>

                                            {/* 程式除錯區塊 */}
                                            <div className="mb-8">
                                                <h2 className={`text-lg font-bold mb-4 flex items-center ${['logic', 'explain_code'].includes(pcData.current_stage) ? 'text-gray-400' : 'text-gray-700'}`}>
                                                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2 ${['logic', 'explain_code'].includes(pcData.current_stage) ? 'bg-gray-200' : 'bg-gray-200 text-gray-600'}`}>2</span>
                                                    程式除錯 (Debugging)
                                                </h2>

                                                {['logic', 'explain_code'].includes(pcData.current_stage) ? (
                                                    <LockedSection />
                                                ) : (
                                                    pcData.question_data.error_code_question.map(q => (
                                                        <QuestionCard key={q.id} question={q} stage="error_code" />
                                                    ))
                                                )}
                                            </div>

                                            {/* 程式碼架構區塊 (Template) */}
                                            <div className="mb-8">
                                                <h2 className={`text-lg font-bold mb-4 flex items-center ${!pcData.is_completed ? 'text-gray-400' : 'text-gray-700'}`}>
                                                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs mr-2 ${!pcData.is_completed ? 'bg-gray-200' : 'bg-gray-200 text-gray-600'}`}>3</span>
                                                    程式碼架構 (Template)
                                                </h2>

                                                {!pcData.is_completed ? (
                                                    <LockedSection />
                                                ) : (
                                                    <div className="animate-fade-in-up">
                                                        <div className="border border-gray-300 rounded-xl overflow-hidden shadow-sm">
                                                            <div className="bg-gray-100 px-4 py-2 border-b border-gray-300 flex justify-between items-center">
                                                                <span className="font-bold text-gray-700 text-sm">📄 Template Code</span>
                                                            </div>
                                                            <pre className="bg-[#1e1e1e] text-gray-100 p-4 text-sm font-mono overflow-auto max-h-[500px] leading-relaxed whitespace-pre">
                                                                {getTemplateContent(pcData.template)}
                                                            </pre>
                                                        </div>

                                                        <div className="mt-6 flex justify-center items-center p-4 bg-green-50 border border-green-200 rounded-xl text-green-700">
                                                            <span className="font-bold">觀念建構已完成！可以開始撰寫程式了。</span>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            {/* 完成後統計區塊 - 顯示首答紀錄與分數 */}
                                            {pcData.is_completed && (
                                                <div className="mb-8 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl shadow-sm">
                                                    <h2 className="text-lg font-bold text-blue-800 mb-4 flex items-center">
                                                        📊 作答紀錄與成績統計
                                                    </h2>

                                                    {/* 分數統計 */}
                                                    {(() => {
                                                        const explainResponses = pcData.student_status.explain_code || [];
                                                        const errorResponses = pcData.student_status.error_code || [];
                                                        const explainQuestions = pcData.question_data.explain_code_question || [];
                                                        const errorQuestions = pcData.question_data.error_code_question || [];

                                                        // 計算首答正確率 (只看每題第一筆)
                                                        const getFirstAttemptResult = (responses: StudentResponse[], qId: string) => {
                                                            return responses.find(r => r.q_id === qId);
                                                        };

                                                        const explainFirstCorrect = explainQuestions.filter(q => {
                                                            const first = getFirstAttemptResult(explainResponses, q.id);
                                                            return first?.is_correct;
                                                        }).length;

                                                        const errorFirstCorrect = errorQuestions.filter(q => {
                                                            const first = getFirstAttemptResult(errorResponses, q.id);
                                                            return first?.is_correct;
                                                        }).length;

                                                        const totalQuestions = explainQuestions.length + errorQuestions.length;
                                                        const totalFirstCorrect = explainFirstCorrect + errorFirstCorrect;

                                                        return (
                                                            <>
                                                                {/* 總分 */}
                                                                <div className="mb-6 p-4 bg-white rounded-lg border border-blue-100 flex items-center justify-between">
                                                                    <span className="text-gray-700 font-medium">🎯 首答正確題數</span>
                                                                    <span className="text-2xl font-bold text-blue-600">
                                                                        {totalFirstCorrect} / {totalQuestions}
                                                                    </span>
                                                                </div>

                                                                {/* 程式碼解釋 - 首答紀錄 */}
                                                                <div className="mb-4">
                                                                    <h3 className="font-semibold text-gray-700 mb-2">📖 程式碼解釋 ({explainFirstCorrect}/{explainQuestions.length})</h3>
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {explainQuestions.map((q, idx) => {
                                                                            const first = getFirstAttemptResult(explainResponses, q.id);
                                                                            const isCorrect = first?.is_correct || false;
                                                                            const optionLetter = first ? String.fromCharCode(64 + first.selected_option_id) : '?';
                                                                            return (
                                                                                <div
                                                                                    key={q.id}
                                                                                    className={`px-3 py-1.5 rounded-lg text-sm font-medium ${isCorrect
                                                                                        ? 'bg-green-100 text-green-700 border border-green-200'
                                                                                        : 'bg-red-100 text-red-700 border border-red-200'
                                                                                        }`}
                                                                                >
                                                                                    Q{idx + 1}: 選 {optionLetter} {isCorrect ? '✅' : '❌'}
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                </div>

                                                                {/* 程式除錯 - 首答紀錄 */}
                                                                <div>
                                                                    <h3 className="font-semibold text-gray-700 mb-2">🐛 程式除錯 ({errorFirstCorrect}/{errorQuestions.length})</h3>
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {errorQuestions.map((q, idx) => {
                                                                            const first = getFirstAttemptResult(errorResponses, q.id);
                                                                            const isCorrect = first?.is_correct || false;
                                                                            const optionLetter = first ? String.fromCharCode(64 + first.selected_option_id) : '?';
                                                                            return (
                                                                                <div
                                                                                    key={q.id}
                                                                                    className={`px-3 py-1.5 rounded-lg text-sm font-medium ${isCorrect
                                                                                        ? 'bg-green-100 text-green-700 border border-green-200'
                                                                                        : 'bg-red-100 text-red-700 border border-red-200'
                                                                                        }`}
                                                                                >
                                                                                    Q{idx + 1}: 選 {optionLetter} {isCorrect ? '✅' : '❌'}
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                </div>
                                                            </>
                                                        );
                                                    })()}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PreCoding;