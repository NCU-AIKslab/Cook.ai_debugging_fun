import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Sidebar from '../../../components/student/debugging/Sidebar';
import { useUser } from '../../../contexts/UserContext';

const API_BASE_URL = "http://127.0.0.1:8000";

// --- Interfaces ---
interface ProblemDetail {
    _id: string;
    title: string;
    description: string;
    input_description: string;
    output_description: string;
    samples: Array<{ input: string; output: string }>;
}

interface ChatMessage {
    role: 'user' | 'agent';
    content: string;
    type?: 'scaffold' | 'chat';
}

interface PracticeOption {
    id: number;
    label: string;
    feedback: string;
}

interface PracticeCode {
    content: string;
    language: string;
}

interface PracticeQuestionContent {
    text: string;
    code?: PracticeCode;
}

interface PracticeConfig {
    correct_id: number;
    explanation: string;
}

interface PracticeItem {
    id: string;
    type: string;
    question: PracticeQuestionContent;
    options: PracticeOption[];
    answer_config: PracticeConfig;
}

interface QuestionAnswerState {
    [key: string]: number;
}

interface QuestionFeedbackState {
    [key: string]: boolean;
}

const StudentCodingHelp: React.FC = () => {
    const { user } = useUser();

    // 從 UserContext 獲取學生資訊
    const student = {
        stu_id: user?.user_id?.toString() || "113522096",
        name: user?.full_name || "Student"
    };

    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [selectedProblemId, setSelectedProblemId] = useState<string | null>(null);
    const [problemData, setProblemData] = useState<ProblemDetail | null>(null);

    const [studentCode, setStudentCode] = useState<string>("");
    const [result, setResult] = useState<string | null>(null);
    const [isAccepted, setIsAccepted] = useState(false);
    const [hasSubmission, setHasSubmission] = useState(false);
    const [loading, setLoading] = useState(false);

    const [activeRightTab, setActiveRightTab] = useState<'editor' | 'chatbot' | 'practice'>('editor');
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState("");
    const [isChatLoading, setIsChatLoading] = useState(false);
    const chatEndRef = useRef<HTMLDivElement>(null);

    // Practice State
    const [practiceList, setPracticeList] = useState<PracticeItem[]>([]);
    const [practiceId, setPracticeId] = useState<number | null>(null);
    // [修改 1] 加入 'no_practice' 狀態
    const [practiceStatus, setPracticeStatus] = useState<'locked' | 'todo' | 'done' | 'no_practice'>('locked');
    const [userAnswers, setUserAnswers] = useState<QuestionAnswerState>({});
    const [feedbackMap, setFeedbackMap] = useState<QuestionFeedbackState>({});

    const [leftWidth, setLeftWidth] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // 用來控制輪詢是否繼續的 Ref
    const isPollingRef = useRef(false);

    const isProblemSelected = !!selectedProblemId;

    useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages, isChatLoading]);

    // Cleanup polling on unmount
    useEffect(() => {
        return () => { isPollingRef.current = false; };
    }, []);

    // Sidebar Dragging Logic
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging || !containerRef.current) return;
            const containerRect = containerRef.current.getBoundingClientRect();
            const newLeftWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
            if (newLeftWidth > 20 && newLeftWidth < 80) setLeftWidth(newLeftWidth);
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

    // 1. 初始化資料
    useEffect(() => {
        const fetchData = async () => {
            if (!selectedProblemId) {
                setProblemData(null);
                setStudentCode("");
                return;
            }

            setLoading(true);
            setResult(null);
            setIsAccepted(false);
            setHasSubmission(false);  // 重置提交狀態

            // 重置 Practice State
            setPracticeStatus('locked');
            setPracticeList([]);
            setPracticeId(null);
            setUserAnswers({});
            setFeedbackMap({});

            setChatMessages([]);
            setActiveRightTab('editor');
            isPollingRef.current = false;

            try {
                const problemRes = await axios.get(`${API_BASE_URL}/debugging/problems/${selectedProblemId}`);
                setProblemData(problemRes.data);

                const codeRes = await axios.get(`${API_BASE_URL}/debugging/student_code/${student.stu_id}/${selectedProblemId}`);
                const { status, data } = codeRes.data;

                if (status === "success") {
                    setStudentCode(data.code || "");
                    setResult(data.result);
                    setIsAccepted(data.is_accepted);
                    // 若有既存結果，表示曾經提交過
                    if (data.result) {
                        setHasSubmission(true);
                    }

                    const pInfo = data.practice;
                    if (data.is_accepted) {
                        if (pInfo && pInfo.exists && pInfo.data && pInfo.data.length > 0) {
                            // 有練習題資料
                            setPracticeList(pInfo.data || []);
                            setPracticeId(pInfo.id);
                            const isCompleted = pInfo.completed;
                            setPracticeStatus(isCompleted ? 'done' : 'todo');

                            if (pInfo.student_answer && Array.isArray(pInfo.student_answer)) {
                                const ansMap: QuestionAnswerState = {};
                                const fbMap: QuestionFeedbackState = {};
                                pInfo.student_answer.forEach((rec: any) => {
                                    ansMap[rec.q_id] = rec.selected_option_id;
                                    if (rec.is_correct) {
                                        fbMap[rec.q_id] = true;
                                    }
                                });
                                setUserAnswers(ansMap);
                                setFeedbackMap(fbMap);
                            }
                        } else {
                            // [修改 2] 已 AC 但無練習題 (一次通過或無錯誤紀錄) -> 設定為 'no_practice'
                            setPracticeStatus('no_practice');
                        }
                    }
                } else {
                    setStudentCode("# Write your code here\n");
                }
            } catch (error) {
                console.error("Fetch data failed:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedProblemId, student.stu_id]);

    // 輪詢函式 (保持不變)
    const pollForAnalysisResult = async (retryCount = 0) => {
        if (!isPollingRef.current) return;
        if (retryCount > 20) {
            setIsChatLoading(false);
            setChatMessages(prev => [...prev, { role: 'agent', content: "AI 回應逾時，請重新整理或稍後再試。", type: 'chat' }]);
            isPollingRef.current = false;
            return;
        }

        try {
            const initRes = await axios.post(`${API_BASE_URL}/debugging/help/init`, {
                student_id: student.stu_id,
                problem_id: selectedProblemId
            });

            const { status, reply } = initRes.data;

            if (status === 'resumed' && reply) {
                setChatMessages([{ role: 'agent', content: reply, type: 'scaffold' }]);
                setIsChatLoading(false);
                isPollingRef.current = false;
            } else if (status === 'pending') {
                setTimeout(() => pollForAnalysisResult(retryCount + 1), 2000);
            } else {
                setIsChatLoading(false);
                if (status === 'no_report') {
                    setChatMessages([{ role: 'agent', content: "目前沒有偵測到錯誤報告，若有問題請重新提交。", type: 'chat' }]);
                }
                isPollingRef.current = false;
            }
        } catch (error) {
            console.error("Polling error:", error);
            setIsChatLoading(false);
            setChatMessages(prev => [...prev, { role: 'agent', content: "請於「程式編碼」分頁提交程式碼。", type: 'chat' }]);
            isPollingRef.current = false;
        }
    };

    // 2. 切換 Tab
    const handleTabChange = async (tab: 'editor' | 'chatbot' | 'practice') => {
        if (!selectedProblemId) return;
        if (tab === 'practice' && practiceStatus === 'locked') return;
        // 鎖定程式修正分頁：若無提交紀錄則不允許切換
        if (tab === 'chatbot' && !hasSubmission) return;

        setActiveRightTab(tab);

        if (tab === 'chatbot' && chatMessages.length === 0) {
            setIsChatLoading(true);
            try {
                const histRes = await axios.get(`${API_BASE_URL}/debugging/help/history/${student.stu_id}/${selectedProblemId}`);
                const history = histRes.data;

                if (history && history.length > 0) {
                    const msgs: ChatMessage[] = [];
                    history.forEach((h: any) => {
                        if (h.student) msgs.push({ role: 'user', content: h.student.content });
                        if (h.agent) msgs.push({ role: 'agent', content: h.agent.content, type: h.agent.type });
                    });
                    setChatMessages(msgs);
                    setIsChatLoading(false);
                } else {
                    if (!isAccepted) {
                        isPollingRef.current = true;
                        pollForAnalysisResult();
                    } else {
                        setChatMessages([{ role: 'agent', content: "恭喜您已通過此題！請前往「練習題」分頁進行練習", type: 'chat' }]);
                        setIsChatLoading(false);
                    }
                }
            } catch (error) {
                setChatMessages([{ role: 'agent', content: "請先提交程式碼後，若有錯誤再進行詢問。", type: 'chat' }]);
                setIsChatLoading(false);
            }
        }
    };

    // 3. Run Code
    const handleRunCode = async () => {
        if (!selectedProblemId || isAccepted) return;

        setLoading(true);
        setResult(null);

        try {
            const payload = {
                problem_id: selectedProblemId,
                student_id: student.stu_id,
                code: studentCode
            };
            const response = await axios.post(`${API_BASE_URL}/debugging/submit`, payload);
            const { verdict, practice_question } = response.data;

            setResult(verdict);
            setHasSubmission(true); // 標記已提交過

            const isAC = verdict === "Accepted" || (typeof verdict === 'string' && verdict.includes("AC"));

            if (isAC) {
                setIsAccepted(true);

                // [修改 3] 處理 AC 後的練習題邏輯
                if (practice_question && Array.isArray(practice_question) && practice_question.length > 0) {
                    // Case A: 有練習題
                    setPracticeList(practice_question);
                    setPracticeStatus('todo');
                    setActiveRightTab('practice');

                    // 取得 ID 以供後續儲存
                    try {
                        const codeRes = await axios.get(`${API_BASE_URL}/debugging/student_code/${student.stu_id}/${selectedProblemId}`);
                        if (codeRes.data.data.practice && codeRes.data.data.practice.id) {
                            setPracticeId(codeRes.data.data.practice.id);
                        }
                    } catch (e) {
                        console.error("Failed to fetch updated practice ID:", e);
                    }
                } else {
                    // Case B: 無練習題 (一次通過)
                    // 設定狀態為 no_practice，並切換分頁顯示綠色勾勾
                    setPracticeList([]);
                    setPracticeStatus('no_practice');
                    setActiveRightTab('practice');
                }
            } else {
                if (response.data.message) {
                    console.log("Backend message:", response.data.message);
                }
            }
            setChatMessages([]);
            isPollingRef.current = false;

        } catch (error: any) {
            console.error("Run code error:", error);
            setResult("System Error");
        } finally {
            setLoading(false);
        }
    };

    // 4. Chat Send (保持不變)
    const handleSendChat = async () => {
        if (!chatInput.trim() || isChatLoading || !selectedProblemId) return;
        const userMsg = chatInput;
        setChatInput("");
        setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        setIsChatLoading(true);

        try {
            const res = await axios.post(`${API_BASE_URL}/debugging/help/chat`, {
                student_id: student.stu_id,
                problem_id: selectedProblemId,
                message: userMsg
            });
            setChatMessages(prev => [...prev, { role: 'agent', content: res.data.reply, type: 'chat' }]);
        } catch (error) {
            setChatMessages(prev => [...prev, { role: 'agent', content: "發生錯誤，請稍後再試。", type: 'chat' }]);
        } finally {
            setIsChatLoading(false);
        }
    };

    // 5. Handle Option Select (保持不變)
    const handleOptionSelect = async (qId: string, optionId: number, correctId: number) => {
        if (feedbackMap[qId]) return;

        setUserAnswers(prev => ({ ...prev, [qId]: optionId }));

        const isCorrect = optionId === correctId;
        if (isCorrect) {
            const newFeedbackMap = { ...feedbackMap, [qId]: true };
            setFeedbackMap(newFeedbackMap);
            const completedCount = Object.keys(newFeedbackMap).length;
            const totalCount = practiceList.length;

            if (completedCount === totalCount) {
                setPracticeStatus('done');
                const finalAnswers = { ...userAnswers, [qId]: optionId };
                await savePracticeResult(finalAnswers, true);
            }
        }
    };

    const savePracticeResult = async (currentAnswers: QuestionAnswerState, isAllDone: boolean) => {
        if (!practiceId) return;
        try {
            const answersPayload = Object.entries(currentAnswers).map(([qid, oid]) => ({
                q_id: qid,
                selected_option_id: oid
            }));

            await axios.post(`${API_BASE_URL}/debugging/practice/submit`, {
                practice_id: practiceId,
                answers: answersPayload
            });
        } catch (error) {
            console.error("Auto save failed", error);
        }
    };

    // UI Helper
    const renderStatus = (status: string | null) => {
        if (!status) return <span className="text-gray-500 font-bold text-xs uppercase">READY</span>;
        let displayStatus = status;
        let color = "bg-gray-400";
        let textColor = "text-gray-600";
        if (status.includes("Accepted") || status.includes("AC")) {
            displayStatus = "Accepted"; color = "bg-green-500"; textColor = "text-green-600";
        } else if (status.includes("Wrong")) {
            displayStatus = "Wrong Answer"; color = "bg-red-500"; textColor = "text-red-600";
        } else if (status.includes("Time")) {
            displayStatus = "Time Limit Exceeded"; color = "bg-orange-500"; textColor = "text-orange-600";
        } else if (status.includes("Runtime") || status.includes("Error")) {
            displayStatus = "Runtime Error"; color = "bg-red-600"; textColor = "text-red-700";
        }
        return (
            <div className="flex items-center space-x-2 animate-fadeIn">
                <div className={`w-3 h-3 rounded-full shadow-sm ${color}`}></div>
                <span className={`font-bold font-mono text-sm ${textColor}`}>{displayStatus}</span>
            </div>
        );
    };

    return (
        <div className="flex h-full w-full bg-white">
            <Sidebar isOpen={isSidebarOpen} selectedProblemId={selectedProblemId} onSelectProblem={setSelectedProblemId} />

            <div className="flex-1 flex flex-col h-full min-w-0">
                {/* Header */}
                <div className="h-12 border-b border-gray-200 flex items-center px-4 bg-white shrink-0 justify-between">
                    <div className="flex items-center">
                        <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="mr-3 text-gray-500 hover:text-gray-700">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                        </button>
                        <h2 className="font-bold text-gray-800">{problemData?.title || '請選擇題目'}</h2>
                    </div>
                </div>

                <div ref={containerRef} className="flex-1 flex overflow-hidden relative">
                    {/* Left: Problem Description */}
                    <div style={{ width: `${leftWidth}%` }} className="flex flex-col border-r border-gray-200 bg-white overflow-y-auto">
                        <div className="p-6">
                            {problemData ? (
                                <div className="prose max-w-none text-sm text-gray-700">
                                    <div className="text-gray-600 text-base" dangerouslySetInnerHTML={{ __html: problemData.description }} />
                                    <h4 className="text-base font-bold mt-4 mb-2">輸入說明</h4>
                                    <div className="text-gray-600 text-base" dangerouslySetInnerHTML={{ __html: problemData.input_description }} />
                                    <h4 className="text-base font-bold mt-4 mb-2">輸出說明</h4>
                                    <div className="text-gray-600 text-base" dangerouslySetInnerHTML={{ __html: problemData.output_description }} />
                                    <div className="mt-6 space-y-4">
                                        {problemData.samples.map((s, i) => (
                                            <div key={i} className="bg-gray-50 p-3 rounded border">
                                                <div className="text-xs font-bold text-gray-500 mb-2">SAMPLE {i + 1}</div>
                                                <div className="space-y-3">
                                                    <div><div className="text-xs text-gray-400 mb-1">INPUT</div><pre className="text-xs bg-white p-2 rounded border overflow-x-auto">{s.input}</pre></div>
                                                    <div><div className="text-xs text-gray-400 mb-1">OUTPUT</div><pre className="text-xs bg-white p-2 rounded border overflow-x-auto">{s.output}</pre></div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : <div className="text-gray-400 text-center mt-10">請從左側列表選擇一個題目</div>}
                        </div>
                    </div>

                    <div className="w-1 bg-gray-200 hover:bg-blue-400 cursor-col-resize z-10" onMouseDown={(e) => { e.preventDefault(); setIsDragging(true); }} />

                    {/* Right: Tabs */}
                    <div style={{ width: `${100 - leftWidth}%` }} className="flex flex-col bg-gray-50 min-w-0">
                        <div className="flex bg-white border-b border-gray-200">
                            <button
                                onClick={() => handleTabChange('editor')}
                                disabled={!isProblemSelected}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors 
                                    ${!isProblemSelected ? 'border-transparent text-gray-300 cursor-not-allowed' : activeRightTab === 'editor' ? 'border-black text-black' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                            >
                                程式編碼
                            </button>

                            <button
                                onClick={() => handleTabChange('chatbot')}
                                disabled={!isProblemSelected || !hasSubmission}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center gap-2
                                    ${!isProblemSelected || !hasSubmission
                                        ? 'border-transparent text-gray-300 cursor-not-allowed'
                                        : activeRightTab === 'chatbot'
                                            ? 'border-blue-500 text-blue-600'
                                            : 'border-transparent text-gray-500 hover:text-gray-700'}`}
                            >
                                <span>程式修正</span>
                            </button>

                            {/* [修改 4] 練習題 Tab 按鈕邏輯更新 */}
                            <button
                                onClick={() => handleTabChange('practice')}
                                disabled={!isProblemSelected || practiceStatus === 'locked'}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center space-x-2 
                                    ${!isProblemSelected
                                        ? 'border-transparent text-gray-300 cursor-not-allowed'
                                        : activeRightTab === 'practice'
                                            ? 'border-green-500 text-green-700'
                                            : practiceStatus === 'locked'
                                                ? 'border-transparent text-gray-300 cursor-not-allowed'
                                                : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                <span>練習題</span>
                                {practiceStatus === 'todo' && <span className="flex items-center justify-center w-4 h-4 rounded-full bg-red-500 text-white text-[10px]">!</span>}
                                {/* 'done' 或 'no_practice' 都顯示勾勾 */}
                                {(practiceStatus === 'done' || practiceStatus === 'no_practice') && <span className="flex items-center justify-center w-4 h-4 rounded-full bg-green-500 text-white text-[10px]">✓</span>}
                            </button>
                        </div>

                        <div className="flex-1 relative overflow-hidden flex flex-col">
                            {activeRightTab === 'editor' && (
                                <>
                                    <div className="flex-1 relative bg-[#1e1e1e]">
                                        <textarea
                                            className={`w-full h-full bg-[#1e1e1e] text-gray-300 font-mono text-sm p-4 outline-none resize-none border-none focus:ring-0 ${(isAccepted || !isProblemSelected) ? 'cursor-not-allowed opacity-80' : ''}`}
                                            value={studentCode}
                                            onChange={(e) => (!isAccepted && isProblemSelected) && setStudentCode(e.target.value)}
                                            spellCheck={false}
                                            readOnly={isAccepted || !isProblemSelected}
                                            placeholder={!isProblemSelected ? "請先從左側選擇題目..." : ""}
                                        />
                                        {isAccepted && <div className="absolute top-4 right-4 bg-green-600 text-white px-3 py-1 text-xs rounded shadow opacity-90">Accepted (Read Only)</div>}
                                    </div>
                                    <div className="bg-white border-t border-gray-200 p-2 flex justify-between items-center h-14">
                                        <div className="px-2">{renderStatus(result)}</div>
                                        <button
                                            onClick={handleRunCode}
                                            disabled={loading || isAccepted || !isProblemSelected}
                                            className={`px-6 py-2 rounded text-sm font-bold text-white transition-colors ${(loading || isAccepted || !isProblemSelected) ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
                                        >
                                            {loading ? 'Running...' : isAccepted ? 'Locked' : 'Run Code'}
                                        </button>
                                    </div>
                                </>
                            )}

                            {activeRightTab === 'chatbot' && (
                                <div className="flex flex-col h-full bg-white">
                                    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                                        {chatMessages.length === 0 && !isChatLoading && <div className="text-center text-gray-400 mt-10">準備載入對話紀錄...</div>}
                                        {chatMessages.map((msg, idx) => (
                                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                                <div className={`max-w-[85%] p-3 rounded-lg text-sm shadow-sm whitespace-pre-wrap ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'}`}>
                                                    {msg.role === 'agent' && <div className="text-xs font-bold text-blue-600 mb-1">System</div>}
                                                    {msg.content}
                                                </div>
                                            </div>
                                        ))}
                                        {isChatLoading && <div className="text-gray-400 text-xs text-center animate-pulse">Thinking...</div>}
                                        <div ref={chatEndRef} />
                                    </div>
                                    <div className="p-3 border-t bg-white flex space-x-2">
                                        <input
                                            className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-gray-100"
                                            placeholder="針對錯誤提問..."
                                            value={chatInput}
                                            onChange={(e) => setChatInput(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                                            disabled={isChatLoading || chatMessages.length === 0 || !isProblemSelected}
                                        />
                                        <button
                                            onClick={handleSendChat}
                                            disabled={isChatLoading || chatMessages.length === 0 || !isProblemSelected}
                                            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:bg-gray-300"
                                        >
                                            Send
                                        </button>
                                    </div>
                                </div>
                            )}

                            {activeRightTab === 'practice' && (
                                <div className="flex flex-col h-full bg-white p-6 overflow-y-auto">
                                    {/* [修改 5] 渲染邏輯更新 */}
                                    {practiceStatus === 'no_practice' ? (
                                        // 無練習題時的畫面
                                        <div className="flex items-center justify-center h-full">
                                            <div className="bg-green-50 border border-green-200 p-6 rounded-lg text-green-800 text-center animate-fadeIn shadow-sm">
                                                <div className="text-4xl mb-3">🎉</div>
                                                <h3 className="text-lg font-bold mb-1">此題無練習題，您已掌握本題觀念！</h3>
                                            </div>
                                        </div>
                                    ) : practiceList.length > 0 ? (
                                        <div className="max-w-3xl mx-auto w-full space-y-8 pb-10">
                                            {practiceStatus === 'done' ? (
                                                <div className="bg-green-50 border border-green-200 p-4 rounded-lg text-green-800 text-sm flex items-center animate-fadeIn">
                                                    <span className="text-2xl mr-3">🎉</span>
                                                    <div>
                                                        <strong>恭喜全數通過！</strong>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg text-blue-800 text-sm flex items-center">
                                                    <span className="text-xl mr-3">💡</span>
                                                    <div>
                                                        <strong>練習題</strong>
                                                        <p>請逐一完成以下題目，答對後系統將自動鎖定該題</p>
                                                    </div>
                                                </div>
                                            )}

                                            {practiceList.map((item, idx) => {
                                                const qId = item.id;
                                                const currentSel = userAnswers[qId];
                                                const isLocked = feedbackMap[qId];

                                                return (
                                                    <div key={qId} className={`bg-white border rounded-xl shadow-sm overflow-hidden transition-all ${isLocked ? 'border-green-200 ring-1 ring-green-100 opacity-80' : 'border-gray-200'}`}>
                                                        <div className={`p-5 border-b border-gray-100 ${isLocked ? 'bg-green-50' : 'bg-gray-50'}`}>
                                                            <div className="flex justify-between items-start">
                                                                <div className="flex space-x-3">
                                                                    <span className={`text-xs font-bold px-2 py-1 rounded h-fit mt-1 ${isLocked ? 'bg-green-200 text-green-800' : 'bg-blue-100 text-blue-800'}`}>
                                                                        {isLocked ? 'COMPLETED' : `Q${idx + 1}`}
                                                                    </span>
                                                                    <div>
                                                                        <h3 className="font-bold text-gray-800 text-lg mb-2">{item.question.text}</h3>
                                                                        {item.question.code && (
                                                                            <pre className="bg-gray-800 text-gray-200 p-3 rounded text-sm font-mono overflow-x-auto">
                                                                                {item.question.code.content}
                                                                            </pre>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>

                                                        <div className="p-5 space-y-4">
                                                            {item.options.map(opt => {
                                                                const isSelected = currentSel === opt.id;
                                                                const isCorrectOption = opt.id === item.answer_config.correct_id;

                                                                let containerClass = "border-gray-200 hover:bg-gray-50";

                                                                if (isLocked) {
                                                                    if (isCorrectOption) {
                                                                        containerClass = "border-green-500 bg-green-50 ring-1 ring-green-500 cursor-default";
                                                                    } else {
                                                                        containerClass = "border-gray-100 opacity-50 cursor-not-allowed";
                                                                    }
                                                                } else {
                                                                    if (isSelected) {
                                                                        if (isCorrectOption) {
                                                                            containerClass = "border-green-500 bg-green-50";
                                                                        } else {
                                                                            containerClass = "border-red-500 bg-red-50 ring-1 ring-red-500";
                                                                        }
                                                                    }
                                                                }

                                                                return (
                                                                    <div key={opt.id}>
                                                                        <label
                                                                            className={`flex items-start p-4 rounded-lg border transition-all ${containerClass} ${isLocked ? '' : 'cursor-pointer'}`}
                                                                            onClick={() => !isLocked && handleOptionSelect(qId, opt.id, item.answer_config.correct_id)}
                                                                        >
                                                                            <div className={`mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center mr-3 shrink-0 ${(isLocked && isCorrectOption) || (isSelected && isCorrectOption) ? 'border-green-600' : isSelected ? 'border-red-500' : 'border-gray-400'}`}>
                                                                                {((isLocked && isCorrectOption) || isSelected) && (
                                                                                    <div className={`w-2 h-2 rounded-full ${(isLocked && isCorrectOption) || (isSelected && isCorrectOption) ? 'bg-green-600' : 'bg-red-500'}`}></div>
                                                                                )}
                                                                            </div>
                                                                            <div className="flex-1">
                                                                                <span className={`text-sm font-medium ${isLocked && !isCorrectOption ? 'text-gray-400' : 'text-gray-700'}`}>{opt.label}</span>
                                                                            </div>
                                                                        </label>
                                                                        {isLocked && isCorrectOption && (
                                                                            <div className="mt-2 ml-8 p-3 bg-green-100 text-green-800 text-sm rounded animate-fadeIn">
                                                                                <strong>✨ Correct!</strong> {item.answer_config.explanation}
                                                                            </div>
                                                                        )}
                                                                        {!isLocked && isSelected && !isCorrectOption && (
                                                                            <div className="mt-2 ml-8 p-3 bg-red-100 text-red-800 text-sm rounded animate-fadeIn">
                                                                                <strong>❌ Incorrect.</strong> {opt.feedback}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-4">
                                            <div className="text-4xl">🤔</div>
                                            <p>正在為您生成客製化練習題...</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StudentCodingHelp;