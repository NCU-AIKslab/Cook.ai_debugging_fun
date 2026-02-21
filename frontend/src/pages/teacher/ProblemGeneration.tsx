import { useState, useEffect } from 'react';
import axios from 'axios';
import API_BASE_URL from '../../config/api';
import Editor from '@monaco-editor/react';
import { ArchitectureEditor, QuestionsListEditor } from './AIGenerationComponents';

interface ProblemData {
    problem_id: string;
    title: string;
    description: string;
    input_description: string;
    output_description: string;
    samples: any[];
    test_cases: any[]; // New
    solution_code: string;
    start_time: string;
    end_time: string;
    judge_type: 'stdio' | 'function';
    entry_point: string;
    hint: string;
    precoding?: {
        explanation?: any;
        debugging?: any;
        architecture?: any;
    };
}

const INITIAL_PROBLEM_DATA: ProblemData = {
    problem_id: '',
    title: '',
    description: '',
    input_description: '',
    output_description: '',
    samples: [],
    test_cases: [],
    solution_code: '',
    start_time: '',
    end_time: '',
    judge_type: 'stdio',
    entry_point: '',
    hint: ''
};

export default function ProblemGeneration() {
    const [problemId, setProblemId] = useState('');
    const [problemData, setProblemData] = useState<ProblemData>(INITIAL_PROBLEM_DATA);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');

    // UI State
    const [activeTab, setActiveTab] = useState<'basic' | 'ai'>('basic');

    // List of existing problems for dropdown
    const [existingProblems, setExistingProblems] = useState<{ problem_id: string, title: string }[]>([]);

    useEffect(() => {
        fetchProblemList();
    }, []);

    const fetchProblemList = async () => {
        try {
            const res = await axios.get(`${API_BASE_URL}/teacher/problem/list`);
            if (res.data.status === 'success') {
                setExistingProblems(res.data.data);
            }
        } catch (error) {
            console.error("Failed to fetch problem list", error);
        }
    };

    // Generation states
    const [genType, setGenType] = useState<'explanation' | 'debugging' | 'architecture'>('explanation');
    const [genContent, setGenContent] = useState('');
    const [genLoading, setGenLoading] = useState(false);

    // Manual Control States
    const [coreConcept, setCoreConcept] = useState<string>('');
    const [allowedScope, setAllowedScope] = useState<string[]>([]);

    // Editor text states
    const [samplesJson, setSamplesJson] = useState('[]');
    const [testCasesJson, setTestCasesJson] = useState('[]');

    const CONCEPTS = [
        { id: 'C1', label: 'C1: 變數與資料型態' },
        { id: 'C2', label: 'C2: 數值與字串運算' },
        { id: 'C3', label: 'C3: List列表' },
        { id: 'C4', label: 'C4: 條件判斷' },
        { id: 'C5', label: 'C5: For迴圈' },
        { id: 'C6', label: 'C6: While迴圈' },
        { id: 'C7', label: 'C7: Dictionary字典' },
        { id: 'C8', label: 'C8: Function函式' },
    ];

    const fetchProblem = async () => {
        if (!problemId) return;
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE_URL}/teacher/problem/${problemId}`);
            if (res.data.status === 'success') {
                const data = res.data.data;
                // Ensure samples is array
                let samples = data.samples;
                if (typeof samples === 'string') {
                    try { samples = JSON.parse(samples); } catch { }
                }

                // Ensure test_cases is array
                let test_cases = data.test_cases;
                if (typeof test_cases === 'string') {
                    try { test_cases = JSON.parse(test_cases); } catch { }
                }

                const loadedData = {
                    problem_id: data._id || data.problem_id,
                    title: data.title || '',
                    description: data.description || '',
                    input_description: data.input_description || '',
                    output_description: data.output_description || '',
                    samples: samples || [],
                    test_cases: test_cases || [],
                    solution_code: data.solution_code || '',
                    start_time: data.start_time || '',
                    end_time: data.end_time || '',
                    judge_type: data.judge_type || 'stdio',
                    entry_point: data.entry_point || '',
                    hint: data.hint || '',
                    precoding: data.precoding || {} // Load precoding
                };

                setProblemData(loadedData);
                setSamplesJson(JSON.stringify(loadedData.samples, null, 2));
                setTestCasesJson(JSON.stringify(loadedData.test_cases, null, 2));

                // Initial load content based on current genType
                if (loadedData.precoding && loadedData.precoding[genType]) {
                    setGenContent(JSON.stringify(loadedData.precoding[genType], null, 2));
                } else {
                    setGenContent('');
                }

                // Reset manual controls on load? Or keep them? 
                // Let's reset to avoid confusion
                setCoreConcept('');
                setAllowedScope([]);

                setMessage('Problem loaded.');
            }
        } catch (error) {
            console.error(error);
            setMessage('Problem not found or error loading.');
        } finally {
            setLoading(false);
        }
    };

    // Fetch specifically updating precoding data (lighter weight if needed, but reusing fetchProblem is safer for consistency)
    // Actually, let's make a specific fetch for just the precoding part to be efficient?
    // The user asked specifically for "auto load database data update" when clicking buttons.
    // Re-fetching the whole problem ensures we have the latest structure.
    // However, to avoid resetting UI state like active tab (which is fine here), let's just create a specialized function or useEffect.

    // Effect: When genType changes (user switches tab), re-fetch data from DB to ensure it is up-to-date.
    useEffect(() => {
        if (problemId && activeTab === 'ai') {
            // We can just call fetchProblem() here, but we might want to avoid full page 'Loading...' overlay if possible.
            // But existing fetchProblem sets 'loading' which disables inputs. This is actually good to prevent edits while loading.
            // Let's use a background fetch or a targeted one to update problemData.precoding.

            const fetchPrecodingData = async () => {
                setGenLoading(true);
                try {
                    const res = await axios.get(`${API_BASE_URL}/teacher/problem/${problemId}`);
                    if (res.data.status === 'success') {
                        const data = res.data.data;
                        // Update local problemData precoding
                        setProblemData(prev => ({
                            ...prev,
                            precoding: data.precoding || {}
                        }));
                    }
                } catch (error) {
                    console.error("Failed to auto-refresh precoding data", error);
                } finally {
                    setGenLoading(false);
                }
            };

            fetchPrecodingData();
        }
    }, [genType, problemId, activeTab]);

    // Update content when switching tabs or problem data changes
    useEffect(() => {
        if (problemData.precoding && problemData.precoding[genType]) {
            setGenContent(JSON.stringify(problemData.precoding[genType], null, 2));
        } else {
            setGenContent('');
        }
    }, [genType, problemData.precoding]);

    const handleSaveProblem = async () => {
        setLoading(true);
        try {
            // Prepare payload
            const payload = {
                ...problemData,
                problem_id: problemId || problemData.problem_id
            };

            // Dates: ensure proper format or null
            if (!payload.start_time) delete (payload as any).start_time;
            if (!payload.end_time) delete (payload as any).end_time;

            await axios.post(`${API_BASE_URL}/teacher/problem/`, payload);
            setMessage('儲存成功');
            fetchProblemList(); // Refresh list
        } catch (error: any) {
            console.error(error);
            setMessage('儲存失敗: ' + (error.response?.data?.detail || error.message));
        } finally {
            setLoading(false);
        }
    };

    const handleNewProblem = () => {
        setProblemId('');
        setProblemData(INITIAL_PROBLEM_DATA);
        setSamplesJson('[]');
        setTestCasesJson('[]');
        setMessage('已清除內容，請輸入新題目資訊');
    };



    const handleGenerate = async () => {
        if (!problemId) return;
        setGenLoading(true);
        try {
            // Include manual settings
            const payload = {
                core_concept: coreConcept || null,
                allowed_scope: allowedScope.length > 0 ? allowedScope : null
            };

            const res = await axios.post(`${API_BASE_URL}/teacher/problem/${problemId}/generate/${genType}`, payload);
            if (res.data.status === 'success') {
                setGenContent(JSON.stringify(res.data.data, null, 2));
                setMessage(`${genType} content generated.`);
            }
        } catch (error: any) {
            console.error(error);
            setMessage('Generation failed: ' + (error.response?.data?.detail || error.message));
        } finally {
            setGenLoading(false);
        }
    };

    const handleSaveGenContent = async () => {
        if (!problemId) return;
        setGenLoading(true);
        try {
            let contentParsed;
            try {
                contentParsed = JSON.parse(genContent);
            } catch (e) {
                setMessage('Invalid JSON in generated content editor.');
                setGenLoading(false);
                return;
            }

            const res = await axios.post(`${API_BASE_URL}/teacher/problem/${problemId}/save/${genType}`, {
                content: contentParsed
            });
            setMessage(res.data.message);

            // Update local state to reflect saved content
            setProblemData(prev => ({
                ...prev,
                precoding: {
                    ...prev.precoding,
                    [genType]: contentParsed
                }
            }));

        } catch (error: any) {
            console.error(error);
            setMessage('Error saving generated content: ' + (error.response?.data?.detail || error.message));
        } finally {
            setGenLoading(false);
        }
    };

    return (
        <div className="p-6 w-full mx-auto">
            <h1 className="text-2xl font-bold mb-6 text-gray-800">題目生成與設定</h1>

            {/* Top Bar: Load Problem */}
            <div className="flex gap-4 mb-6 bg-white p-4 rounded-lg shadow-sm items-center flex-wrap">
                <div className="flex items-center gap-2">
                    <label className="text-sm font-medium">選擇既有題目：</label>
                    <select
                        className="border p-2 rounded w-64"
                        onChange={(e) => {
                            if (e.target.value) {
                                setProblemId(e.target.value);
                            }
                        }}
                        value={existingProblems.find(p => p.problem_id === problemId) ? problemId : ''}
                    >
                        <option value="">-- 請選擇題目 --</option>
                        {existingProblems.map(p => (
                            <option key={p.problem_id} value={p.problem_id}>
                                {p.problem_id} - {p.title.length > 20 ? p.title.substring(0, 20) + '...' : p.title}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex items-center gap-2">
                    <label className="text-sm font-medium">或輸入 ID：</label>
                    <input
                        type="text"
                        placeholder="輸入題目 ID"
                        className="border p-2 rounded w-48"
                        value={problemId}
                        onChange={(e) => setProblemId(e.target.value)}
                    />
                </div>

                <button
                    onClick={fetchProblem}
                    className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
                    disabled={loading || !problemId}
                >
                    讀取 (Load)
                </button>

                <button
                    onClick={handleNewProblem}
                    className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                >
                    新增題目 (New)
                </button>



                <span className="text-sm text-gray-600 ml-2">{message}</span>
            </div>

            {/* Tabs */}
            <div className="flex border-b mb-6">
                <button
                    className={`px-6 py-2 font-medium ${activeTab === 'basic' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('basic')}
                >
                    基本資訊 (Basic Info)
                </button>
                <button
                    className={`px-6 py-2 font-medium ${activeTab === 'ai' ? 'border-b-2 border-purple-600 text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
                    onClick={() => setActiveTab('ai')}
                >
                    AI 題目生成 (AI Generation)
                </button>
            </div>

            {/* Content Area */}
            {activeTab === 'basic' && (
                <div className="w-full">
                    {/* Full Width Problem Details */}
                    <div className="bg-white p-6 rounded-lg shadow-sm space-y-4">
                        <h2 className="text-xl font-semibold mb-4 border-b pb-2">基本資訊編輯</h2>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-medium mb-1">題目 ID (Problem ID)</label>
                                <input
                                    className="w-full border p-2 rounded bg-white hover:bg-gray-50"
                                    value={problemId}
                                    onChange={(e) => setProblemId(e.target.value)}
                                    placeholder="輸入新 ID 或讀取既有 ID"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">標題 (Title)</label>
                                <input
                                    className="w-full border p-2 rounded"
                                    value={problemData.title}
                                    onChange={(e) => setProblemData({ ...problemData, title: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-medium mb-1">開始時間 (Start Time - 可見)</label>
                                <input
                                    type="datetime-local"
                                    className="w-full border p-2 rounded"
                                    value={problemData.start_time ? problemData.start_time.slice(0, 16) : ''}
                                    onChange={(e) => setProblemData({ ...problemData, start_time: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">結束時間 (End Time - 可見)</label>
                                <input
                                    type="datetime-local"
                                    className="w-full border p-2 rounded"
                                    value={problemData.end_time ? problemData.end_time.slice(0, 16) : ''}
                                    onChange={(e) => setProblemData({ ...problemData, end_time: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-medium mb-1">評測類型 (Judge Type)</label>
                                <select
                                    className="w-full border p-2 rounded"
                                    value={problemData.judge_type}
                                    onChange={(e) => setProblemData({ ...problemData, judge_type: e.target.value as 'stdio' | 'function' })}
                                >
                                    <option value="stdio">Standard I/O (stdio)</option>
                                    <option value="function">Function Call</option>
                                </select>
                            </div>
                            {problemData.judge_type === 'function' && (
                                <div>
                                    <label className="block text-sm font-medium mb-1">進入點函式 (Entry Point)</label>
                                    <input
                                        className="w-full border p-2 rounded"
                                        placeholder="e.g. solve"
                                        value={problemData.entry_point}
                                        onChange={(e) => setProblemData({ ...problemData, entry_point: e.target.value })}
                                    />
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-1">題目描述 (Markdown)</label>
                            <textarea
                                className="w-full border p-2 rounded h-32 font-mono text-sm"
                                value={problemData.description}
                                onChange={(e) => setProblemData({ ...problemData, description: e.target.value })}
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">輸入說明 (Input Description)</label>
                                <textarea
                                    className="w-full border p-2 rounded h-24 font-mono text-sm"
                                    value={problemData.input_description}
                                    onChange={(e) => setProblemData({ ...problemData, input_description: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">輸出說明 (Output Description)</label>
                                <textarea
                                    className="w-full border p-2 rounded h-24 font-mono text-sm"
                                    value={problemData.output_description}
                                    onChange={(e) => setProblemData({ ...problemData, output_description: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">範例測資 (Samples - JSON Array)</label>
                                <div className="h-48 border rounded overflow-hidden">
                                    <Editor
                                        height="100%"
                                        defaultLanguage="json"
                                        value={samplesJson}
                                        onChange={(val: string | undefined) => {
                                            const value = val || '';
                                            setSamplesJson(value);
                                            try {
                                                const parsed = JSON.parse(value);
                                                setProblemData(prev => ({ ...prev, samples: parsed }));
                                            } catch (err) { }
                                        }}
                                        options={{ minimap: { enabled: false }, fontSize: 12 }}
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">評測測資 (Test Cases - Hidden JSON Array)</label>
                                <div className="h-48 border rounded overflow-hidden">
                                    <Editor
                                        height="100%"
                                        defaultLanguage="json"
                                        value={testCasesJson}
                                        onChange={(val: string | undefined) => {
                                            const value = val || '';
                                            setTestCasesJson(value);
                                            try {
                                                const parsed = JSON.parse(value);
                                                setProblemData(prev => ({ ...prev, test_cases: parsed }));
                                            } catch (err) { }
                                        }}
                                        options={{ minimap: { enabled: false }, fontSize: 12 }}
                                    />
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-1">提示 (Hint)</label>
                            <textarea
                                className="w-full border p-2 rounded h-20 font-mono text-sm"
                                value={problemData.hint}
                                onChange={(e) => setProblemData({ ...problemData, hint: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-1">參考解答 / 架構來源 (Solution Code)</label>
                            <div className="h-64 border rounded overflow-hidden">
                                <Editor
                                    height="100%"
                                    defaultLanguage="python"
                                    value={problemData.solution_code}
                                    onChange={(val: string | undefined) => setProblemData({ ...problemData, solution_code: val || '' })}
                                    options={{ minimap: { enabled: false }, fontSize: 12 }}
                                />
                            </div>
                        </div>

                        <button
                            onClick={handleSaveProblem}
                            className="w-full bg-green-600 text-white py-3 rounded hover:bg-green-700 disabled:opacity-50 font-bold text-lg"
                            disabled={loading}
                        >
                            {loading ? '儲存中...' : '儲存基本資訊 (Save Basic Info)'}
                        </button>
                    </div>
                </div>
            )}

            {activeTab === 'ai' && (
                <div className="bg-white p-6 rounded-lg shadow-sm space-y-4 flex flex-col h-full">
                    <h2 className="text-xl font-semibold mb-4 border-b pb-2">AI 題目生成 (AI Generation)</h2>

                    {/* New Manual Controls */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4 p-4 bg-gray-50 rounded border">
                        <div>
                            <label className="block text-sm font-medium mb-2">核心概念 (Core Concept) - 可選</label>
                            <select
                                className="w-full border p-2 rounded bg-white"
                                value={coreConcept}
                                onChange={(e) => setCoreConcept(e.target.value)}
                            >
                                <option value="">-- 自動判斷 (Auto) --</option>
                                {CONCEPTS.map(c => (
                                    <option key={c.id} value={c.id}>{c.label}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">允許使用的語法範圍 (Allowed Scope) - 可選</label>
                            <div className="flex flex-wrap gap-2">
                                {CONCEPTS.map(c => (
                                    <label key={c.id} className="flex items-center space-x-1 cursor-pointer bg-white p-1 rounded border hover:bg-gray-100">
                                        <input
                                            type="checkbox"
                                            value={c.id}
                                            checked={allowedScope.includes(c.id)}
                                            onChange={(e) => {
                                                if (e.target.checked) {
                                                    setAllowedScope([...allowedScope, c.id]);
                                                } else {
                                                    setAllowedScope(allowedScope.filter(id => id !== c.id));
                                                }
                                            }}
                                            className="rounded"
                                        />
                                        <span className="text-xs">{c.id}</span>
                                    </label>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-2 mb-2">
                        {['explanation', 'debugging', 'architecture'].map((t) => (
                            <button
                                key={t}
                                onClick={() => {
                                    setGenType(t as any);
                                }}
                                className={`px-4 py-2 rounded capitalize ${genType === t ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>

                    <div className="flex-1 flex flex-col">
                        <div className="flex justify-between items-center mb-2">
                            <span className="text-sm font-medium text-gray-600">目前生成內容 (Generated Content) - {genType}</span>
                            <div className="space-x-2 flex items-center">
                                <button
                                    onClick={handleGenerate}
                                    className="px-3 py-1 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:opacity-50"
                                    disabled={genLoading || !problemId}
                                >
                                    {genLoading ? '生成中...' : '開始生成 (Start Generation)'}
                                </button>
                                <button
                                    onClick={handleSaveGenContent}
                                    className="px-3 py-1 bg-teal-600 text-white rounded text-sm hover:bg-teal-700 disabled:opacity-50"
                                    disabled={genLoading || !problemId}
                                >
                                    儲存內容 (Save Content)
                                </button>
                            </div>
                        </div>

                        {/* ... existing generated content display ... */}
                        <div className="flex-1 border rounded overflow-hidden min-h-[500px] p-4 relative bg-gray-50 overflow-y-auto">
                            {!genContent ? (
                                <div className="flex items-center justify-center h-full text-gray-500">
                                    No content generated yet. Click "Start Generation".
                                </div>
                            ) : (
                                (() => {
                                    try {
                                        const parsed = JSON.parse(genContent);
                                        if (genType === 'architecture') {
                                            return <ArchitectureEditor data={parsed} onChange={(d) => setGenContent(JSON.stringify(d, null, 2))} />;
                                        } else {
                                            return <QuestionsListEditor data={parsed} type={genType as any} onChange={(d) => setGenContent(JSON.stringify(d, null, 2))} />;
                                        }
                                    } catch (e) {
                                        return (
                                            <div className="flex flex-col h-full gap-2">
                                                <div className="text-red-500 p-2 bg-red-50 rounded">
                                                    Failed to parse JSON for structured view. You can edit the raw JSON below to fix it.
                                                </div>
                                                <Editor
                                                    height="100%"
                                                    defaultLanguage="json"
                                                    value={genContent}
                                                    onChange={(val: string | undefined) => setGenContent(val || '')}
                                                    options={{ minimap: { enabled: false }, fontSize: 12, wordWrap: 'on' }}
                                                />
                                            </div>
                                        );
                                    }
                                })()
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
