import React, { useState, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import Spinner from '../common/Spinner';
import { ReportContainer } from '../reports/ReportContainer';
import { FaPaperPlane, FaStop } from 'react-icons/fa';

interface ChatInterfaceProps {
  selectedUniqueContentIds: number[];
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ selectedUniqueContentIds }) => {
  const [query, setQuery] = useState('');
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: async ({ prompt, unique_content_id, user_id }: { prompt: string; unique_content_id: number; user_id: number }) => {
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ prompt, unique_content_id, user_id }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error('Failed to get AI response');
        }
        return response.json();
      } catch (e: any) {
        if (e.name === 'AbortError') {
          console.log('Fetch aborted by user');
          return { aborted: true };
        } else {
          throw e;
        }
      } finally {
        abortControllerRef.current = null;
      }
    },
    onSuccess: (apiResponse) => {
      if (apiResponse && 'aborted' in apiResponse && apiResponse.aborted) {
        setChatHistory((prev) => [...prev, { type: 'info', text: 'AI 生成已取消' }]);
        return;
      }
      setChatHistory((prev) => [...prev, { type: 'ai', content: apiResponse.result }]);
    },
    onError: (err: any) => {
      if (err.name !== 'AbortError') {
        setChatHistory((prev) => [...prev, { type: 'error', text: err.message }]);
      }
    },
    onSettled: () => {
      abortControllerRef.current = null;
    }
  });

  const handleSendQuery = () => {
    if (!query.trim()) return;
    if (selectedUniqueContentIds.length === 0) {
      alert('請至少選擇一個參考資料！');
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setChatHistory((prev) => [...prev, { type: 'info', text: '正在取消先前的 AI 生成...' }]);
    }

    setChatHistory((prev) => [...prev, { type: 'user', text: query }]);
    const currentQuery = query;

    setQuery('');

    const uniqueContentIdToSend = selectedUniqueContentIds[0];
    console.log('Sending unique_content_id:', uniqueContentIdToSend);

    if (uniqueContentIdToSend === undefined || uniqueContentIdToSend === null || uniqueContentIdToSend === 0) {
      alert('選取的來源出錯!');
      return;
    }

    mutate({ prompt: currentQuery, unique_content_id: uniqueContentIdToSend, user_id: 1 });

    if (selectedUniqueContentIds.length > 1) {
      alert('注意：後端目前僅處理第一個選取的來源。');
    }
  };

  const shouldRender = (apiResult: any) => {
    if (!apiResult || !apiResult.display_type) {
      return false;
    }

    if (apiResult.display_type === 'text_message') {
      const messageText = apiResult.content;
      return typeof messageText === 'string' && messageText.trim().length > 0;
    }

    if (apiResult.display_type === 'exam_questions' || apiResult.display_type === 'summary_report') {
      const data = apiResult.content.data || apiResult.content;
      return (Array.isArray(data) && data.length > 0) || (typeof data === 'object' && data !== null && Object.keys(data).length > 0);
    }

    return true;
  };

  return (
    <div className="flex flex-col h-full p-6">
      {/* Chat history */}
      <div className="flex-1 py-4 overflow-y-auto space-y-4">
        {chatHistory.map((msg, index) => {
          if (msg.type === 'user') {
            return (
              <div key={index} className="flex justify-end">
                <div className="inline-block max-w-[70%] px-4 py-3 rounded-xl bg-theme-primary text-white shadow-sm">
                  {msg.text}
                </div>
              </div>
            );
          } else if (msg.type === 'ai') {
            if (!shouldRender(msg.content)) {
              return null;
            }
            return (
              <div key={index} className="flex justify-start">
                <div className="max-w-[85%]">
                  <ReportContainer result={msg.content} />
                </div>
              </div>
            );
          } else if (msg.type === 'error') {
            return (
              <div key={index} className="flex justify-start">
                <div className="px-4 py-3 bg-destructive-light text-destructive rounded-xl">
                  錯誤: {msg.text}
                </div>
              </div>
            );
          } else if (msg.type === 'info') {
            return (
              <div key={index} className="text-center text-sm text-neutral-text-tertiary py-2">
                {msg.text}
              </div>
            );
          }
          return null;
        })}

        {isPending && (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        )}
        {isError && (
          <div className="p-4 bg-destructive-light text-destructive rounded-lg">
            錯誤: {error?.message || '未知錯誤'}
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 mt-auto">
        <div className="flex items-center gap-3 px-4 py-3 bg-white rounded-xl shadow-card border border-neutral-border">
          <input
            type="text"
            className="flex-1 py-2 border-none focus:ring-0 text-neutral-text-main placeholder:text-neutral-text-tertiary bg-transparent"
            placeholder="請輸入你的指令，例如：幫我出 10 題選擇題"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendQuery();
              }
            }}
            disabled={isPending}
          />
          <button
            onClick={isPending ? () => abortControllerRef.current?.abort() : handleSendQuery}
            disabled={!query.trim() && !isPending}
            className={`
              w-11 h-11 rounded-full flex items-center justify-center
              transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2
              ${isPending
                ? 'bg-neutral-icon text-white hover:bg-neutral-icon-hover focus:ring-neutral-icon'
                : 'bg-theme-primary text-white hover:bg-theme-primary-hover hover:-translate-y-0.5 focus:ring-theme-primary'
              }
              ${(!query.trim() && !isPending) && 'opacity-50 cursor-not-allowed'}
            `}
            aria-label={isPending ? '停止' : '傳送'}
          >
            {isPending ? <FaStop className="w-4 h-4" /> : <FaPaperPlane className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;

