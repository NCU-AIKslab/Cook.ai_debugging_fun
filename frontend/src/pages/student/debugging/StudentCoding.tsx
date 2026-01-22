import React, { useState } from 'react';
import PreCoding from './StudentPreCoding';
import CodingHelp from './StudentCodingHelp';

// 定義學生資料型別
export interface Student {
    stu_id: string;
    name: string;
}

const StudentCoding = () => {
    // 1. 分頁狀態
    const [activeTab, setActiveTab] = useState<'pre-coding' | 'coding-help'>('pre-coding');

    // 2. 寫死 Student 資料 (模擬登入)
    const student: Student = {
        stu_id: "113522096",
        name: "Joyce"
    };

    return (
        <div className="flex flex-col -m-6 w-[calc(100%+3rem)] h-[calc(100vh-64px)] bg-white">

            {/* 分頁導覽列 (Tabs) - 移除 px-6 讓底線滿版 */}
            <div className="border-b border-gray-200 bg-white shrink-0 z-10 pl-6">
                <nav className="-mb-px flex space-x-6">
                    <button
                        onClick={() => setActiveTab('pre-coding')}
                        className={`py-3 px-2 border-b-2 font-medium text-sm transition-colors ${activeTab === 'pre-coding'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        Pre-Coding
                    </button>
                    <button
                        onClick={() => setActiveTab('coding-help')}
                        className={`py-3 px-2 border-b-2 font-medium text-sm transition-colors ${activeTab === 'coding-help'
                            ? 'border-red-500 text-red-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        CodingHelp (程式求救)
                    </button>
                </nav>
            </div>

            {/* 主要內容區塊 - 填滿剩餘高度 */}
            <div className="flex-1 overflow-hidden relative bg-white">
                {activeTab === 'pre-coding' && (
                    <div className="absolute inset-0">
                        <PreCoding student={student} />
                    </div>
                )}

                {activeTab === 'coding-help' && (
                    <div className="absolute inset-0">
                        <CodingHelp student={student} />
                    </div>
                )}
            </div>
        </div>
    );
};

export default StudentCoding;