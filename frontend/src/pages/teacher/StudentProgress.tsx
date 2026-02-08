import React, { useState, useEffect } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config/api';

// ==========================================
// Types
// ==========================================

interface FirstAttempt {
    q_id: string;
    selected_option_id: number;
    is_correct: boolean;
}

interface StudentPrecodingData {
    student_id: string;
    logic_completed: boolean;
    explain_code: {
        first_attempts: FirstAttempt[];
        score: string;
        final_correct: string;
    };
    error_code: {
        first_attempts: FirstAttempt[];
        score: string;
        final_correct: string;
    };
    is_completed: boolean;
}

interface OptionStat {
    option_id: number;
    label: string;
    count: number;
}

interface QuestionStat {
    q_id: string;
    question_text: string;
    options: OptionStat[];
}

interface PrecodingDashboardData {
    status: string;
    students: StudentPrecodingData[];
    question_stats: {
        explain_code: QuestionStat[];
        error_code: QuestionStat[];
    };
}

interface StudentCodingHelpData {
    student_id: string;
    current_verdict: string;
    practice_status: string;
}

interface CodingHelpDashboardData {
    status: string;
    students: StudentCodingHelpData[];
    verdict_stats: Record<string, number>;
}

// ==========================================
// Component
// ==========================================

interface ProblemItem {
    problem_id: string;
    title: string;
}

const StudentProgress: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'precoding' | 'coding_help'>('precoding');
    const [problemId, setProblemId] = useState<string>('');
    const [problemList, setProblemList] = useState<ProblemItem[]>([]);
    const [precodingData, setPrecodingData] = useState<PrecodingDashboardData | null>(null);
    const [codingHelpData, setCodingHelpData] = useState<CodingHelpDashboardData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 學生詳情彈窗狀態
    const [selectedStudent, setSelectedStudent] = useState<StudentPrecodingData | null>(null);
    const [refreshKey, setRefreshKey] = useState(0);

    // Fetch problem list on mount
    useEffect(() => {
        const fetchProblems = async () => {
            try {
                const res = await axios.get<{ status: string; problems: ProblemItem[] }>(
                    `${API_BASE_URL}/dashboard/problems`
                );
                if (res.data.status === 'success' && res.data.problems.length > 0) {
                    setProblemList(res.data.problems);
                    setProblemId(res.data.problems[0].problem_id); // 預設選第一個
                }
            } catch (err) {
                console.error('Failed to fetch problem list:', err);
            }
        };
        fetchProblems();
    }, []);

    // Fetch data when tab or problemId changes
    useEffect(() => {
        if (!problemId) return; // 等待問題列表載入完成

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                if (activeTab === 'precoding') {
                    const res = await axios.get<PrecodingDashboardData>(
                        `${API_BASE_URL}/dashboard/precoding?problem_id=${problemId}`
                    );
                    setPrecodingData(res.data);
                } else {
                    const res = await axios.get<CodingHelpDashboardData>(
                        `${API_BASE_URL}/dashboard/coding_help?problem_id=${problemId}`
                    );
                    setCodingHelpData(res.data);
                }
            } catch (err: any) {
                setError(err.response?.data?.detail || err.message || '載入失敗');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [activeTab, problemId, refreshKey]);

    // 重新整理函數
    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    // Verdict 顏色
    const getVerdictColor = (verdict: string) => {
        switch (verdict) {
            case 'AC': return 'text-green-600 bg-green-100';
            case 'WA': return 'text-red-600 bg-red-100';
            case 'TLE': return 'text-yellow-600 bg-yellow-100';
            case 'RE': return 'text-purple-600 bg-purple-100';
            default: return 'text-gray-600 bg-gray-100';
        }
    };

    // 練習題狀態顏色
    const getPracticeStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'text-green-600';
            case 'todo': return 'text-yellow-600';
            default: return 'text-gray-400';
        }
    };

    return (
        <div className="p-6 bg-gray-50 min-h-full">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800 mb-2">📊 學生答題情況</h1>
                    <p className="text-gray-600">查看學生答題進度與統計數據</p>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2 shadow-sm"
                >
                    <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    重新整理
                </button>
            </div>

            {/* Problem ID Selector */}
            <div className="mb-6 flex items-center">
                <label className="text-gray-700 mr-3 font-medium">選擇題目:</label>
                <select
                    value={problemId}
                    onChange={(e) => setProblemId(e.target.value)}
                    className="bg-white text-gray-800 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm min-w-[300px]"
                >
                    {problemList.length === 0 && (
                        <option value="">載入中...</option>
                    )}
                    {problemList.map((p) => (
                        <option key={p.problem_id} value={p.problem_id}>
                            {p.problem_id} {p.title}
                        </option>
                    ))}
                </select>
            </div>

            {/* Tab Navigation */}
            <div className="flex space-x-3 mb-6">
                <button
                    onClick={() => setActiveTab('precoding')}
                    className={`px-5 py-2.5 rounded-lg font-medium transition-all ${activeTab === 'precoding'
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-100'
                        }`}
                >
                    📝 Intention
                </button>
                <button
                    onClick={() => setActiveTab('coding_help')}
                    className={`px-5 py-2.5 rounded-lg font-medium transition-all ${activeTab === 'coding_help'
                        ? 'bg-blue-600 text-white shadow-md'
                        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-100'
                        }`}
                >
                    💻 CodingHelp
                </button>
            </div>

            {/* Loading / Error */}
            {loading && (
                <div className="flex justify-center items-center py-12">
                    <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500"></div>
                </div>
            )}

            {error && (
                <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded-lg mb-6">
                    ⚠️ {error}
                </div>
            )}

            {/* Pre-coding Tab Content */}
            {!loading && !error && activeTab === 'precoding' && precodingData && (
                <div className="space-y-6">
                    {/* Student Table */}
                    <div className="bg-white rounded-xl p-6 shadow-md border border-gray-200">
                        <h2 className="text-lg font-semibold text-gray-800 mb-4">👥 學生進度</h2>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="border-b border-gray-200 bg-gray-50">
                                        <th className="py-3 px-4 text-gray-600 font-medium">學生 ID</th>
                                        <th className="py-3 px-4 text-gray-600 font-medium">觀念建構</th>
                                        <th className="py-3 px-4 text-gray-600 font-medium">首答正確題數</th>
                                        <th className="py-3 px-4 text-gray-600 font-medium">完成狀態</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {precodingData.students.map((student) => {
                                        // 計算合併分數
                                        const parseScore = (s: string) => {
                                            const match = s.match(/^(\d+)\/(\d+)$/);
                                            return match ? { correct: parseInt(match[1]), total: parseInt(match[2]) } : { correct: 0, total: 0 };
                                        };
                                        const explainScore = parseScore(student.explain_code.score);
                                        const errorScore = parseScore(student.error_code.score);
                                        const totalCorrect = explainScore.correct + errorScore.correct;
                                        const totalQuestions = explainScore.total + errorScore.total;

                                        return (
                                            <tr key={student.student_id} className="border-b border-gray-100 hover:bg-gray-50">
                                                <td className="py-3 px-4">
                                                    <button
                                                        onClick={() => setSelectedStudent(student)}
                                                        className="text-blue-600 hover:text-blue-800 hover:underline font-mono font-medium"
                                                    >
                                                        {student.student_id}
                                                    </button>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <span className={`px-2 py-1 rounded text-sm ${student.logic_completed
                                                        ? 'bg-green-100 text-green-700'
                                                        : 'bg-yellow-100 text-yellow-700'
                                                        }`}>
                                                        {student.logic_completed ? '完成' : '進行中'}
                                                    </span>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <span className="text-lg font-bold text-blue-600">
                                                        {totalCorrect} / {totalQuestions}
                                                    </span>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <span className={`px-2 py-1 rounded text-sm ${student.is_completed
                                                        ? 'bg-green-100 text-green-700'
                                                        : 'bg-gray-100 text-gray-500'
                                                        }`}>
                                                        {student.is_completed ? '完成' : '未完成'}
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {precodingData.students.length === 0 && (
                                        <tr>
                                            <td colSpan={4} className="py-8 text-center text-gray-500">
                                                暫無學生資料
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Question Stats */}
                    <div className="grid md:grid-cols-2 gap-6">
                        {/* Explain Code Stats */}
                        <div className="bg-white rounded-xl p-6 shadow-md border border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4">📖 解釋程式碼 - 選項分佈</h3>
                            {precodingData.question_stats.explain_code.map((q) => (
                                <div key={q.q_id} className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                                    <p className="text-gray-700 text-sm mb-2 font-mono">{q.q_id}</p>
                                    <div className="space-y-2">
                                        {q.options.map((opt) => (
                                            <div key={opt.option_id} className="flex items-center">
                                                <span className="w-8 text-gray-500 text-sm">{opt.option_id}.</span>
                                                <div className="flex-1 bg-gray-200 rounded-full h-4 mr-3">
                                                    <div
                                                        className="bg-blue-500 h-4 rounded-full transition-all"
                                                        style={{ width: `${Math.min(opt.count * 20, 100)}%` }}
                                                    ></div>
                                                </div>
                                                <span className="text-gray-700 text-sm w-8 font-medium">{opt.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {precodingData.question_stats.explain_code.length === 0 && (
                                <p className="text-gray-500 text-center py-4">暫無題目資料</p>
                            )}
                        </div>

                        {/* Error Code Stats */}
                        <div className="bg-white rounded-xl p-6 shadow-md border border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-800 mb-4">🐛 程式除錯 - 選項分佈</h3>
                            {precodingData.question_stats.error_code.map((q) => (
                                <div key={q.q_id} className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                                    <p className="text-gray-700 text-sm mb-2 font-mono">{q.q_id}</p>
                                    <div className="space-y-2">
                                        {q.options.map((opt) => (
                                            <div key={opt.option_id} className="flex items-center">
                                                <span className="w-8 text-gray-500 text-sm">{opt.option_id}.</span>
                                                <div className="flex-1 bg-gray-200 rounded-full h-4 mr-3">
                                                    <div
                                                        className="bg-orange-500 h-4 rounded-full transition-all"
                                                        style={{ width: `${Math.min(opt.count * 20, 100)}%` }}
                                                    ></div>
                                                </div>
                                                <span className="text-gray-700 text-sm w-8 font-medium">{opt.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                            {precodingData.question_stats.error_code.length === 0 && (
                                <p className="text-gray-500 text-center py-4">暫無題目資料</p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* CodingHelp Tab Content */}
            {!loading && !error && activeTab === 'coding_help' && codingHelpData && (
                <div className="space-y-6">
                    {/* Verdict Stats Summary */}
                    <div className="bg-white rounded-xl p-6 shadow-md border border-gray-200">
                        <h2 className="text-lg font-semibold text-gray-800 mb-4">📈 提交結果統計</h2>
                        <div className="flex flex-wrap gap-4">
                            {Object.entries(codingHelpData.verdict_stats).map(([verdict, count]) => (
                                <div key={verdict} className={`px-6 py-4 rounded-lg ${getVerdictColor(verdict)}`}>
                                    <span className="text-2xl font-bold">{count}</span>
                                    <span className="ml-2 font-medium">{verdict}</span>
                                </div>
                            ))}
                            {Object.keys(codingHelpData.verdict_stats).length === 0 && (
                                <p className="text-gray-500">暫無提交紀錄</p>
                            )}
                        </div>
                    </div>

                    {/* Student Table */}
                    <div className="bg-white rounded-xl p-6 shadow-md border border-gray-200">
                        <h2 className="text-lg font-semibold text-gray-800 mb-4">👥 學生提交狀態</h2>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="border-b border-gray-200 bg-gray-50">
                                        <th className="py-3 px-4 text-gray-600 font-medium">學生 ID</th>
                                        <th className="py-3 px-4 text-gray-600 font-medium">目前狀態</th>
                                        <th className="py-3 px-4 text-gray-600 font-medium">練習題</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {codingHelpData.students.map((student) => (
                                        <tr key={student.student_id} className="border-b border-gray-100 hover:bg-gray-50">
                                            <td className="py-3 px-4 text-gray-800 font-mono">{student.student_id}</td>
                                            <td className="py-3 px-4">
                                                <span className={`px-3 py-1 rounded-lg text-sm font-medium ${getVerdictColor(student.current_verdict)}`}>
                                                    {student.current_verdict}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4">
                                                <span className={getPracticeStatusColor(student.practice_status)}>
                                                    {student.practice_status === 'completed' && '已完成'}
                                                    {student.practice_status === 'todo' && '待完成'}
                                                    {student.practice_status === 'no_practice' && '—'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    {codingHelpData.students.length === 0 && (
                                        <tr>
                                            <td colSpan={3} className="py-8 text-center text-gray-500">
                                                暫無學生資料
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* 學生詳情 Modal */}
            {selectedStudent && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedStudent(null)}>
                    <div
                        className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-gray-800">
                                📋 學生詳情: {selectedStudent.student_id}
                            </h2>
                            <button
                                onClick={() => setSelectedStudent(null)}
                                className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
                            >
                                ×
                            </button>
                        </div>

                        {/* 程式碼解釋 - 首答紀錄 */}
                        <div className="mb-6">
                            <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                📖 程式碼解釋 首答紀錄
                                <span className="text-sm font-normal text-gray-500">({selectedStudent.explain_code.score})</span>
                            </h3>
                            <div className="flex flex-wrap gap-3">
                                {selectedStudent.explain_code.first_attempts.length > 0 ? (
                                    selectedStudent.explain_code.first_attempts.map((attempt, idx) => {
                                        const optionLetter = String.fromCharCode(64 + attempt.selected_option_id);
                                        return (
                                            <div
                                                key={attempt.q_id}
                                                className={`px-4 py-2 rounded-lg border ${attempt.is_correct
                                                    ? 'bg-green-50 border-green-200 text-green-700'
                                                    : 'bg-red-50 border-red-200 text-red-700'
                                                    }`}
                                            >
                                                <span className="font-medium">Q{idx + 1}:</span>
                                                <span className="ml-2">選 {optionLetter} {attempt.is_correct ? '✅' : '❌'}</span>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <span className="text-gray-400">尚無作答紀錄</span>
                                )}
                            </div>
                        </div>

                        {/* 程式除錯 - 首答紀錄 */}
                        <div className="mb-6">
                            <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                                🐛 程式除錯 首答紀錄
                                <span className="text-sm font-normal text-gray-500">({selectedStudent.error_code.score})</span>
                            </h3>
                            <div className="flex flex-wrap gap-3">
                                {selectedStudent.error_code.first_attempts.length > 0 ? (
                                    selectedStudent.error_code.first_attempts.map((attempt, idx) => {
                                        const optionLetter = String.fromCharCode(64 + attempt.selected_option_id);
                                        return (
                                            <div
                                                key={attempt.q_id}
                                                className={`px-4 py-2 rounded-lg border ${attempt.is_correct
                                                    ? 'bg-green-50 border-green-200 text-green-700'
                                                    : 'bg-red-50 border-red-200 text-red-700'
                                                    }`}
                                            >
                                                <span className="font-medium">Q{idx + 1}:</span>
                                                <span className="ml-2">選 {optionLetter} {attempt.is_correct ? '✅' : '❌'}</span>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <span className="text-gray-400">尚無作答紀錄</span>
                                )}
                            </div>
                        </div>

                        {/* 狀態摘要 */}
                        <div className="pt-4 border-t border-gray-200">
                            <div className="flex items-center gap-6">
                                <div>
                                    <span className="text-gray-500 text-sm">觀念建構:</span>
                                    <span className={`ml-2 px-2 py-1 rounded text-sm ${selectedStudent.logic_completed
                                        ? 'bg-green-100 text-green-700'
                                        : 'bg-yellow-100 text-yellow-700'
                                        }`}>
                                        {selectedStudent.logic_completed ? '完成' : '進行中'}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-gray-500 text-sm">整體狀態:</span>
                                    <span className={`ml-2 px-2 py-1 rounded text-sm ${selectedStudent.is_completed
                                        ? 'bg-green-100 text-green-700'
                                        : 'bg-gray-100 text-gray-500'
                                        }`}>
                                        {selectedStudent.is_completed ? '完成' : '未完成'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default StudentProgress;
