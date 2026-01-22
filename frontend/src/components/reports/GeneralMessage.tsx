// frontend/src/components/reports/GeneralMessage.tsx

import React from 'react';

interface GeneralMessageProps {
    // 這裡接收的是 apiResult.content，即 { type: string; title: string; content: string }
    // 我們需要訪問的是內層的 'content' 屬性
    content: string;
}

export const GeneralMessage: React.FC<GeneralMessageProps> = ({ content }) => {
    return (
        <div className="p-3 bg-gray-100 rounded-lg">
            <p className="text-gray-800 whitespace-pre-wrap">
                {content} {/* 🎯 修正為 content.content */}
            </p>
        </div>
    );
};