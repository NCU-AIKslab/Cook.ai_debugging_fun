import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Sidebar from '../../../components/student/debugging/Sidebar';
import { useUser } from '../../../contexts/UserContext';
import API_BASE_URL from '../../../config/api';
import Editor from 'react-simple-code-editor';
// @ts-ignore
import { highlight, languages } from 'prismjs';
import 'prismjs/components/prism-python';
import 'prismjs/themes/prism-tomorrow.css';

// --- Interfaces ---
interface ProblemDetail {
    _id: string;
    title: string;
    description: string;
    input_description: string;
    output_description: string;
    samples: Array<{ input: string; output: string }>;
    start_time?: string; // ISO string
    end_time?: string;   // ISO string
}

interface ChatMessage {
    role: 'user' | 'agent';
    content: string;
    zpd?: number;
    timestamp?: string;
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
    // 新增 'generating' 狀態用於背景生成練習題時
    const [practiceStatus, setPracticeStatus] = useState<'locked' | 'todo' | 'done' | 'no_practice' | 'generating'>('locked');
    const [userAnswers, setUserAnswers] = useState<QuestionAnswerState>({});
    const [feedbackMap, setFeedbackMap] = useState<QuestionFeedbackState>({});

    const [leftWidth, setLeftWidth] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // ★ 多題並行輪詢架構 ★
    // activePollingSet: 追蹤哪些題目正在輪詢中（支援多題同時求救）
    const activePollingSet = useRef<Set<string>>(new Set());
    const isPracticePollingRef = useRef(false);
    const selectedProblemIdRef = useRef<string | null>(null);

    // 同步更新 ref（render 期間，比 useEffect 更早）
    selectedProblemIdRef.current = selectedProblemId;

    // ★ React derived state pattern ★
    // 切題時立即清除舊 UI（paint 之前），根據 activePollingSet 推斷 loading
    const [renderedProblemId, setRenderedProblemId] = useState(selectedProblemId);
    if (renderedProblemId !== selectedProblemId) {
        setRenderedProblemId(selectedProblemId);
        setChatMessages([]);
        setIsChatLoading(activePollingSet.current.has(selectedProblemId ?? ''));
    }

    const [canRequestHelp, setCanRequestHelp] = useState(false);

    // V2 State: Track submission version
    const [latestSubmissionNum, setLatestSubmissionNum] = useState<number>(0);
    // V3: Track which submission the current help session belongs to
    const [activeHelpNum, setActiveHelpNum] = useState<number>(0);

    const isProblemSelected = !!selectedProblemId;

    // Time Limit Logic
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

    useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages, isChatLoading]);

    // Cleanup polling on unmount
    useEffect(() => {
        return () => {
            activePollingSet.current.clear();
            isPracticePollingRef.current = false;
        };
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
            setCanRequestHelp(false); // Reset help availability

            // 重置 Practice State
            setPracticeStatus('locked');
            setPracticeList([]);
            setPracticeId(null);
            setUserAnswers({});
            setFeedbackMap({});

            setChatMessages([]);
            setIsChatLoading(activePollingSet.current.has(selectedProblemId));
            setActiveRightTab('editor'); // V3: Reset to editor tab on problem change

            try {
                const problemRes = await axios.get(`${API_BASE_URL}/debugging/problems/${selectedProblemId}`);
                setProblemData(problemRes.data);

                const codeRes = await axios.get(`${API_BASE_URL}/debugging/student_code/${student.stu_id}/${selectedProblemId}`);
                const { status, data } = codeRes.data;

                if (status === "success") {
                    setStudentCode(data.code || "");
                    setResult(data.result);
                    setIsAccepted(data.is_accepted);

                    // V2: Update State
                    setLatestSubmissionNum(data.submission_num || 0);

                    if (data.result) {
                        setHasSubmission(true);

                        // V3 Logic: Enable help button if not accepted and has a submission
                        if (!data.is_accepted && data.submission_num > 0) {
                            // Check if this submission already has a report
                            const subNum = data.submission_num || 0;
                            const repNum = data.latest_report_num || 0;
                            setCanRequestHelp(subNum > repNum);
                        } else {
                            setCanRequestHelp(false);
                        }
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

                // ★ 切回時自動偵測 help 狀態 ★
                // 若此題正在背景輪詢中 → 保持 loading（已由 derived state 設定）
                // 若此題有已完成的 help 結果 → 自動載入
                if (!data?.is_accepted && data?.submission_num > 0) {
                    const subNum = data.submission_num || 0;
                    const repNum = data.latest_report_num || 0;
                    if (subNum <= repNum && !activePollingSet.current.has(selectedProblemId)) {
                        // 此提交已有報告，嘗試載入聊天紀錄
                        try {
                            const historyRes = await axios.get(
                                `${API_BASE_URL}/debugging/help/history/${student.stu_id}/${selectedProblemId}`,
                                { params: { submission_num: subNum } }
                            );
                            // 再次確認仍在此題
                            if (selectedProblemIdRef.current === selectedProblemId) {
                                const chatLog = historyRes.data.chat_log || [];
                                if (chatLog.length > 0) {
                                    const msgs: ChatMessage[] = chatLog.map((msg: any) => ({
                                        role: msg.role as 'user' | 'agent',
                                        content: msg.content,
                                        zpd: msg.zpd,
                                        timestamp: msg.timestamp,
                                        type: msg.type
                                    }));
                                    setChatMessages(msgs);
                                    setActiveHelpNum(subNum);
                                    // 不自動跳到 chatbot tab，讓使用者保持在編碼頁面
                                }
                            }
                        } catch (e) {
                            // 靜默失敗，不影響主流程
                        }
                    }
                }
            } catch (error) {
                console.error("Fetch data failed:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedProblemId, student.stu_id]);

    // ★ 每題獨立輪詢函式 ★
    // forProblemId: 此輪詢所屬的題目（不依賴 closure 或 singleton ref）
    const pollForAnalysisResult = async (targetNum: number, forProblemId: string, retryCount = 0) => {
        // 若此題已從 polling set 移除（例如被新的 help request 取代），停止
        if (!activePollingSet.current.has(forProblemId)) return;

        if (retryCount > 60) {
            activePollingSet.current.delete(forProblemId);
            if (selectedProblemIdRef.current === forProblemId) {
                setIsChatLoading(false);
                setChatMessages(prev => [...prev, { role: 'agent', content: "AI 回應逾時，請重新整理或稍後再試。", type: 'chat' }]);
                setCanRequestHelp(true);
            }
            return;
        }

        try {
            const initRes = await axios.post(`${API_BASE_URL}/debugging/help/init`, {
                student_id: student.stu_id,
                problem_id: forProblemId,
                submission_num: targetNum
            });

            // 輪詢期間可能已被取消
            if (!activePollingSet.current.has(forProblemId)) return;

            const { status, reply, chat_log } = initRes.data;
            const isViewing = selectedProblemIdRef.current === forProblemId;

            if (status === 'resumed') {
                activePollingSet.current.delete(forProblemId);
                if (isViewing) {
                    if (chat_log && chat_log.length > 0) {
                        const msgs: ChatMessage[] = chat_log.map((msg: any) => ({
                            role: msg.role as 'user' | 'agent',
                            content: msg.content,
                            zpd: msg.zpd,
                            timestamp: msg.timestamp,
                            type: msg.type
                        }));
                        setChatMessages(msgs);
                    } else if (reply) {
                        setChatMessages([{ role: 'agent', content: reply, type: 'scaffold' }]);
                    }
                    setIsChatLoading(false);
                }
                // 不在此題 → 結果留在後端，切回時 fetchData 會載入
            } else if (status === 'pending' || status === 'started') {
                // 繼續輪詢（不管使用者在看哪題）
                setTimeout(() => pollForAnalysisResult(targetNum, forProblemId, retryCount + 1), 2000);
            } else {
                activePollingSet.current.delete(forProblemId);
                if (isViewing) {
                    setIsChatLoading(false);
                    if (status === 'no_report') {
                        setChatMessages([{ role: 'agent', content: "目前沒有偵測到錯誤報告，若有問題請重新提交。", type: 'chat' }]);
                    }
                }
            }
        } catch (error) {
            console.error("Polling error:", error);
            activePollingSet.current.delete(forProblemId);
            if (selectedProblemIdRef.current === forProblemId) {
                setIsChatLoading(false);
                setChatMessages(prev => [...prev, { role: 'agent', content: "請於「程式編碼」分頁提交程式碼。", type: 'chat' }]);
                setCanRequestHelp(true);
            }
        }
    };

    // 練習題輪詢函式 (用於背景生成場景)
    const pollForPractice = async (retryCount = 0) => {
        if (!isPracticePollingRef.current) return;
        if (retryCount > 30) {
            // 超時處理：如果30次輪詢後仍無練習題，視為無練習題
            setPracticeStatus('no_practice');
            isPracticePollingRef.current = false;
            return;
        }

        try {
            const codeRes = await axios.get(`${API_BASE_URL}/debugging/student_code/${student.stu_id}/${selectedProblemId}`);
            const { data } = codeRes.data;
            const pInfo = data?.practice;

            if (pInfo && pInfo.exists) {
                if (pInfo.data && pInfo.data.length > 0) {
                    // 練習題已生成 (有題目)
                    setPracticeList(pInfo.data);
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
                    // exists=true 但 data=[] → 無練習題 (後端已確認無報告)
                    setPracticeStatus('no_practice');
                }
                isPracticePollingRef.current = false;
            } else {
                // exists=false → 練習題尚未生成，繼續輪詢
                setTimeout(() => pollForPractice(retryCount + 1), 2000);
            }
        } catch (error) {
            console.error("Practice polling error:", error);
            setTimeout(() => pollForPractice(retryCount + 1), 2000);
        }
    };

    // Phase 8: Manual Request Help
    // Phase 8: Manual Request Help
    const handleRequestHelp = async () => {
        if (!canRequestHelp || isChatLoading || !selectedProblemId || timeStatus !== 'active') return;

        const requestProblemId = selectedProblemId;
        setCanRequestHelp(false);
        setIsChatLoading(true);
        setChatMessages([]);

        const helpNum = latestSubmissionNum;
        setActiveHelpNum(helpNum);

        try {
            const initRes = await axios.post(`${API_BASE_URL}/debugging/help/init`, {
                student_id: student.stu_id,
                problem_id: requestProblemId,
                force_refresh: true,
                submission_num: helpNum
            });

            const isViewing = selectedProblemIdRef.current === requestProblemId;
            const { status, chat_log, reply } = initRes.data;

            if (status === 'resumed') {
                if (isViewing) {
                    if (chat_log && chat_log.length > 0) {
                        const msgs: ChatMessage[] = chat_log.map((msg: any) => ({
                            role: msg.role as 'user' | 'agent',
                            content: msg.content,
                            zpd: msg.zpd,
                            timestamp: msg.timestamp,
                            type: msg.type
                        }));
                        setChatMessages(msgs);
                    } else if (reply) {
                        setChatMessages([{ role: 'agent', content: reply, type: 'scaffold' }]);
                    }
                    setIsChatLoading(false);
                }
            } else if (status === 'started' || status === 'pending') {
                // 加入 polling set 並開始獨立輪詢
                activePollingSet.current.add(requestProblemId);
                pollForAnalysisResult(helpNum, requestProblemId);
            } else {
                if (isViewing) {
                    setChatMessages([{ role: 'agent', content: "目前無錯誤報告。", type: 'chat' }]);
                    setIsChatLoading(false);
                }
            }
        } catch (error) {
            console.error("Request help failed:", error);
            if (selectedProblemIdRef.current === requestProblemId) {
                setChatMessages([{ role: 'agent', content: "請求失敗，請稍後再試。", type: 'chat' }]);
                setIsChatLoading(false);
                setCanRequestHelp(true);
            }
        }
    };

    // 2. 切換 Tab (Modified: Load chat history on chatbot tab)
    const handleTabChange = async (tab: 'editor' | 'chatbot' | 'practice') => {
        if (!selectedProblemId) return;
        if (tab === 'practice' && practiceStatus === 'locked') return;
        // 鎖定程式修正分頁：若無提交紀錄則不允許切換
        if (tab === 'chatbot' && !hasSubmission) return;

        setActiveRightTab(tab);

        // V3: When switching to chatbot tab, load existing chat history
        if (tab === 'chatbot' && chatMessages.length === 0 && !isChatLoading) {
            const tabProblemId = selectedProblemId;
            try {
                const historyRes = await axios.get(
                    `${API_BASE_URL}/debugging/help/history/${student.stu_id}/${tabProblemId}`,
                    { params: { submission_num: latestSubmissionNum || undefined } }
                );
                // 守衛：API 期間可能已切題
                if (selectedProblemIdRef.current !== tabProblemId) return;
                const chatLog = historyRes.data.chat_log || [];
                if (chatLog.length > 0) {
                    const msgs: ChatMessage[] = chatLog.map((msg: any) => ({
                        role: msg.role as 'user' | 'agent',
                        content: msg.content,
                        zpd: msg.zpd,
                        timestamp: msg.timestamp,
                        type: msg.type
                    }));
                    setChatMessages(msgs);
                    // Set activeHelpNum to the submission that has this history
                    setActiveHelpNum(latestSubmissionNum);
                }
            } catch (e) {
                console.error("Failed to load chat history:", e);
            }
        }
    };

    // 3. Run Code
    const handleRunCode = async () => {
        if (!selectedProblemId || isAccepted || timeStatus !== 'active') return;

        setLoading(true);
        setResult(null);

        try {
            const payload = {
                problem_id: selectedProblemId,
                student_id: student.stu_id,
                code: studentCode
            };
            const response = await axios.post(`${API_BASE_URL}/debugging/submit`, payload);
            const { verdict, practice_question, submission_num: newSubNum } = response.data;

            setResult(verdict);
            setHasSubmission(true); // 標記已提交過

            // V3 Fix: Update latestSubmissionNum from backend response
            // This is CRITICAL for snapshot polling to work correctly
            if (newSubNum) {
                setLatestSubmissionNum(newSubNum);
            }

            const isAC = verdict === "Accepted" || (typeof verdict === 'string' && verdict.includes("AC"));

            if (isAC) {
                setIsAccepted(true);
                setCanRequestHelp(false); // Lock help button

                // 處理 AC 後的練習題邏輯
                if (practice_question && Array.isArray(practice_question) && practice_question.length > 0) {
                    // Case A: 有練習題 (立即回傳)
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
                    // Case B: 練習題正在背景生成中
                    // 設定狀態為 generating，並開始輪詢
                    setPracticeList([]);
                    setPracticeStatus('generating');
                    setActiveRightTab('practice');
                    isPracticePollingRef.current = true;
                    pollForPractice();
                }
            } else {
                // Wrong Answer / Error
                setCanRequestHelp(true); // Enable help button
                if (response.data.message) {
                    console.log("Backend message:", response.data.message);
                }
            }
            // shouldRefreshChatRef logic removed as we manually request help now

        } catch (error: any) {
            console.error("Run code error:", error);
            setResult("System Error");
        } finally {
            setLoading(false);
        }
    };

    // 4. Chat Send
    const handleSendChat = async () => {
        if (!chatInput.trim() || isChatLoading || !selectedProblemId || timeStatus !== 'active') return;
        const userMsg = chatInput;
        const requestProblemId = selectedProblemId; // 捕獲當前題目
        setChatInput("");
        setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        setIsChatLoading(true);

        try {
            // V3: Send activeHelpNum so backend saves to the correct dialogue
            const res = await axios.post(`${API_BASE_URL}/debugging/help/chat`, {
                student_id: student.stu_id,
                problem_id: requestProblemId, // 使用捕獲值，非 closure
                message: userMsg,
                submission_num: activeHelpNum
            });
            // 守衛：若已切題則不更新 UI
            if (selectedProblemIdRef.current !== requestProblemId) return;
            setChatMessages(prev => [...prev, { role: 'agent', content: res.data.reply, type: 'chat' }]);
        } catch (error) {
            if (selectedProblemIdRef.current !== requestProblemId) return;
            setChatMessages(prev => [...prev, { role: 'agent', content: "發生錯誤，請稍後再試。", type: 'chat' }]);
        } finally {
            if (selectedProblemIdRef.current === requestProblemId) {
                setIsChatLoading(false);
            }
        }
    };

    // 5. Handle Option Select (保持不變)
    const handleOptionSelect = async (qId: string, optionId: number, correctId: number) => {
        if (feedbackMap[qId] || timeStatus !== 'active') return;

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
                await savePracticeResult(finalAnswers);
            }
        }
    };

    const savePracticeResult = async (currentAnswers: QuestionAnswerState) => {
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
        <div className="flex h-[calc(100vh-60px)] w-full bg-white">
            <Sidebar isOpen={isSidebarOpen} selectedProblemId={selectedProblemId} onSelectProblem={setSelectedProblemId} />

            <div className="flex-1 flex flex-col h-full min-w-0">
                {/* Header */}
                <div className="h-12 border-b border-gray-200 flex items-center px-4 bg-white shrink-0 justify-between">
                    <div className="flex items-center">
                        <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="mr-3 text-gray-500 hover:text-gray-700">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
                        </button>
                        <h2 className="font-bold text-gray-800 flex items-center gap-2">
                            {problemData?.title || '請選擇題目'}
                            {timeStatus === 'ended' && <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded border border-red-200">Time's Up</span>}
                            {timeStatus === 'not_started' && <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded border border-yellow-200">未開始 (Not Started)</span>}
                        </h2>
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
                                disabled={!isProblemSelected || !hasSubmission || loading || timeStatus !== 'active'}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center gap-2
                                    ${!isProblemSelected || !hasSubmission || loading || timeStatus !== 'active'
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
                                disabled={!isProblemSelected || practiceStatus === 'locked' || timeStatus !== 'active'}
                                className={`flex-1 py-3 text-sm font-bold border-b-2 transition-colors flex items-center justify-center space-x-2 
                                    ${!isProblemSelected || timeStatus !== 'active'
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
                                {practiceStatus === 'generating' && <span className="flex items-center justify-center w-4 h-4 rounded-full bg-yellow-500 text-white text-[10px] animate-pulse">⏳</span>}
                                {/* 'done' 或 'no_practice' 都顯示勾勾 */}
                                {(practiceStatus === 'done' || practiceStatus === 'no_practice') && <span className="flex items-center justify-center w-4 h-4 rounded-full bg-green-500 text-white text-[10px]">✓</span>}
                            </button>
                        </div>

                        <div className="flex-1 relative overflow-hidden flex flex-col">
                            {activeRightTab === 'editor' && (
                                <>
                                    <div className="flex-1 relative bg-[#1e1e1e] overflow-auto">
                                        <Editor
                                            value={studentCode}
                                            onValueChange={(code) => (!isAccepted && isProblemSelected && timeStatus === 'active') && setStudentCode(code)}
                                            highlight={(code) => highlight(code, languages.python, 'python')}
                                            padding={16}
                                            readOnly={isAccepted || !isProblemSelected || timeStatus !== 'active'}
                                            placeholder={!isProblemSelected ? "請先從左側選擇題目..." : timeStatus === 'not_started' ? "考試尚未開始。" : timeStatus === 'ended' ? "時間已結束，無法作答。" : "# Write your code here\n"}
                                            tabSize={4}
                                            insertSpaces={true}
                                            style={{
                                                fontFamily: '"Fira Code", "Fira Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace',
                                                fontSize: 14,
                                                lineHeight: 1.6,
                                                minHeight: '100%',
                                                backgroundColor: '#1e1e1e',
                                                color: '#d4d4d4',
                                            }}
                                            className={`${(isAccepted || !isProblemSelected || timeStatus !== 'active') ? 'cursor-not-allowed opacity-80' : ''}`}
                                        />
                                        {isAccepted && <div className="absolute top-4 right-4 bg-green-600 text-white px-3 py-1 text-xs rounded shadow opacity-90">Accepted (Read Only)</div>}
                                        {timeStatus === 'ended' && !isAccepted && <div className="absolute top-4 right-4 bg-red-600 text-white px-3 py-1 text-xs rounded shadow opacity-90">Time's Up (Locked)</div>}
                                        {timeStatus === 'not_started' && <div className="absolute top-4 right-4 bg-yellow-600 text-white px-3 py-1 text-xs rounded shadow opacity-90">Not Started (Locked)</div>}
                                    </div>
                                    <div className="bg-white border-t border-gray-200 p-2 flex justify-between items-center h-14">
                                        <div className="px-2">{renderStatus(result)}</div>
                                        <button
                                            onClick={handleRunCode}
                                            disabled={loading || isAccepted || !isProblemSelected || timeStatus !== 'active'}
                                            className={`px-6 py-2 rounded text-sm font-bold text-white transition-colors ${(loading || isAccepted || !isProblemSelected || timeStatus !== 'active') ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
                                        >
                                            {loading ? 'Running...' : isAccepted ? 'Locked' : timeStatus === 'ended' ? 'Expired' : timeStatus === 'not_started' ? 'Not Started' : 'Run Code'}
                                        </button>
                                    </div>
                                </>
                            )}

                            {activeRightTab === 'chatbot' && (
                                <div className="flex flex-col h-full bg-white">
                                    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                                        {(isAccepted || (chatMessages.length === 0 && !isChatLoading)) && (
                                            <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                                                {isAccepted ? (
                                                    <div className="bg-green-50 border border-green-200 p-6 rounded-lg text-green-800 text-center animate-fadeIn shadow-sm">
                                                        <h3 className="text-lg font-bold mb-1">程式正確請前往練習題頁面</h3>
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div className="text-4xl">🤖</div>
                                                        <div className="text-center">
                                                            <p className="font-medium">遇到困難了嗎？</p>
                                                            <p className="text-sm text-gray-400 mt-1">
                                                                {canRequestHelp
                                                                    ? "點擊下方「求救」按鈕，讓 AI 幫您分析錯誤"
                                                                    : "請先提交程式碼，若有錯誤即可使用求救功能"}
                                                            </p>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        )}
                                        {!isAccepted && chatMessages.map((msg, idx) => (
                                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                                <div className={`max-w-[85%] p-3 rounded-lg text-sm shadow-sm whitespace-pre-wrap break-words break-all ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-white border border-gray-200 text-gray-800 rounded-bl-none'}`}>
                                                    {msg.role === 'agent' && <div className="text-xs font-bold text-blue-600 mb-1">System</div>}
                                                    {msg.content}
                                                </div>
                                            </div>
                                        ))}
                                        {isChatLoading && <div className="text-gray-400 text-xs text-center animate-pulse">Thinking...</div>}
                                        <div ref={chatEndRef} />
                                    </div>
                                    <div className="p-3 border-t bg-white space-y-3">
                                        <button
                                            onClick={handleRequestHelp}
                                            disabled={!canRequestHelp || isChatLoading || isAccepted}
                                            className={`w-full py-2 rounded-lg text-sm font-bold flex items-center justify-center transition-all
                                                ${!canRequestHelp || isChatLoading || isAccepted
                                                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
                                                    : 'bg-yellow-500 hover:bg-yellow-600 text-white shadow-sm hover:shadow'}`}
                                        >
                                            {isAccepted ? (
                                                <>
                                                    <span className="mr-2">✨</span>
                                                    程式已正確
                                                </>
                                            ) : (
                                                <>
                                                    求救
                                                </>
                                            )}
                                        </button>

                                        <div className="flex space-x-2">
                                            <textarea
                                                className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 disabled:bg-gray-100 resize-none h-10 min-h-[40px] max-h-[120px] overflow-y-auto"
                                                placeholder={isAccepted ? "題目已通過，無法繼續對話" : chatMessages.length === 0 ? "請先點擊求救按鈕..." : "針對錯誤提問..."}
                                                value={chatInput}
                                                onChange={(e) => setChatInput(e.target.value)}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter' && !e.shiftKey) {
                                                        e.preventDefault();
                                                        if (!isAccepted && chatMessages.length > 0) {
                                                            handleSendChat();
                                                        }
                                                    }
                                                }}
                                                disabled={isChatLoading || chatMessages.length === 0 || !isProblemSelected || isAccepted}
                                            />
                                            <button
                                                onClick={handleSendChat}
                                                disabled={isChatLoading || chatMessages.length === 0 || !isProblemSelected || isAccepted}
                                                className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:bg-gray-300"
                                            >
                                                Send
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeRightTab === 'practice' && (
                                <div className="flex flex-col h-full bg-white p-6 overflow-y-auto">
                                    {/* 練習題生成中 */}
                                    {practiceStatus === 'generating' ? (
                                        <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                                            <div className="text-4xl animate-bounce">🤔</div>
                                            <p className="text-lg font-medium">正在為您生成客製化練習題...</p>
                                            <p className="text-sm text-gray-400">請稍候，AI 正在根據您的錯誤歷史設計題目</p>
                                            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                                        </div>
                                    ) : practiceStatus === 'no_practice' ? (
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
                                                    <div key={qId} className={`bg-white border rounded-xl shadow-sm overflow-hidden transition-all ${isLocked ? 'bg-green-50 border-green-200 shadow-sm' : 'border-gray-200'}`}>
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
                                                                        containerClass = "bg-green-600 text-white border-green-600 font-medium cursor-default";
                                                                    } else if (isSelected) {
                                                                        containerClass = "bg-red-300 text-white border-red-300 font-medium cursor-not-allowed";
                                                                    } else {
                                                                        containerClass = "bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed opacity-50";
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
                                                                            <div className={`mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center mr-3 shrink-0 ${(isLocked && isCorrectOption) ? 'border-white' : (isLocked && isSelected) ? 'border-white' : (isSelected && isCorrectOption) ? 'border-green-600' : isSelected ? 'border-red-500' : 'border-gray-400'}`}>
                                                                                {((isLocked && isCorrectOption) || isSelected) && (
                                                                                    <div className={`w-2 h-2 rounded-full ${(isLocked && isCorrectOption) ? 'bg-white' : (isLocked && isSelected) ? 'bg-white' : (isSelected && isCorrectOption) ? 'bg-green-600' : 'bg-red-500'}`}></div>
                                                                                )}
                                                                            </div>
                                                                            <div className="flex-1">
                                                                                <span className={`text-sm font-medium ${isLocked && isCorrectOption ? 'text-white' : isLocked && isSelected ? 'text-white' : isLocked ? 'text-gray-400' : 'text-gray-700'}`}>{opt.label}</span>
                                                                            </div>
                                                                        </label>
                                                                        {isLocked && isCorrectOption && (
                                                                            <div className="mt-2 ml-8 p-3 bg-green-100 text-green-800 text-sm rounded animate-fadeIn">
                                                                                <strong>✨ Correct!</strong> {item.answer_config.explanation}
                                                                            </div>
                                                                        )}
                                                                        {!isLocked && isSelected && !isCorrectOption && (
                                                                            <div className="mt-2 ml-8 p-3 bg-red-100 text-red-800 text-sm rounded animate-fadeIn">
                                                                                {opt.feedback}
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