import React from 'react';

interface InfoBlockItem {
  id: string;
  text: string;
  link?: string;
  isNew?: boolean;
}

interface InfoBlockProps {
  title: string;
  items: InfoBlockItem[];
}

const InfoBlock: React.FC<InfoBlockProps> = ({ title, items }) => {
  // 未來可能針對不同功能的訊息框做設計，例如公告、作業不同
  return (
    <div className="mt-8">
      <h3 className="mb-6 border-b border-gray-200 pb-4 text-lg text-gray-800 font-bold">{title}</h3>
      {
        items.length > 0 ? (
          <ul className="list-none p-0 m-0 text-sm">
            {items.map((item) => (
              <li key={item.id} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-b-0">
                {item.link ? (
                  <a href={item.link} className="no-underline text-gray-500 transition-colors hover:text-blue-500">
                    {item.text}
                  </a>
                ) : (
                  <span>{item.text}</span>
                )}
                {item.isNew && (
                  <span className="bg-red-500 text-white text-xs font-bold py-0.5 px-1.5 rounded">New</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-400 py-2 m-0 italic">目前沒有任何項目。</p>
        )
      }
    </div>
  );
};

export default InfoBlock;