// TeacherAICenter.py
import React, { useState, useEffect, useCallback, useRef } from 'react';
import SourcePanel from './SourcePanel';
import ChatInterface from './ChatInterface';

export type Source = {
  id: string;
  name: string;
  unique_content_id: number;
};

const TeacherAICenter: React.FC = () => {
  const [selectedSources, setSelectedSources] = useState<string[]>([]); // Changed to store unique_content_id (number)
  const [sources, setSources] = useState<Source[]>([]);
  const [panelWidth, setPanelWidth] = useState(320);
  const isResizing = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null); // Ref for the main container

  const fetchSources = useCallback(async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/materials?course_id=1');
      if (!response.ok) {
        throw new Error('Failed to fetch sources');
      }
      const data = await response.json();
      setSources(data.map((item: any) => ({
        id: String(item.id),
        name: item.file_name, // Explicitly map file_name to name
        unique_content_id: item.unique_content_id
      })));
    } catch (error) {
      console.error("Error fetching sources:", error);
    }
  }, []);
  useEffect(() => {
    fetchSources();
  }, []);

  const handleSelectSource = (uniqueContentId: number) => { // Expect uniqueContentId as number
    console.log("handleSelectSource received uniqueContentId:", uniqueContentId);
    console.log("Current sources array:", sources);

    const selectedSource = sources.find(s => s.unique_content_id === uniqueContentId); // Find by unique_content_id
    console.log("Result of sources.find for uniqueContentId:", selectedSource);

    if (!selectedSource) {
      console.error("Error: selectedSource is undefined for uniqueContentId:", uniqueContentId);
      return;
    }

    setSelectedSources(prev => {
      if (prev.includes(selectedSource.unique_content_id)) {
        return prev.filter(id => id !== selectedSource.unique_content_id);
      } else {
        return [...prev, selectedSource.unique_content_id];
      }
    });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current || !containerRef.current) return;

    // --- Bug Fix: Calculate width relative to the container ---
    const containerStart = containerRef.current.getBoundingClientRect().left;
    const newWidth = e.clientX - containerStart;

    if (newWidth > 90 && newWidth < 600) { // Min 80px, Max 600px
      setPanelWidth(newWidth);
    }
  }, []);

  const handleMouseUp = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseMove]);

  return (
    <div className="flex w-full h-full bg-white" ref={containerRef}>
      <div style={{ width: `${panelWidth}px` }} className="flex-shrink-0 h-full">
        <SourcePanel
          availableSources={sources}
          selectedSources={selectedSources}
          onSelectSource={handleSelectSource}
          onUploadSuccess={fetchSources}
        />
      </div>

      <div
        className="w-2 h-full cursor-col-resize flex items-center justify-center group"
        onMouseDown={handleMouseDown}
      >
        <div className="w-px h-16 bg-neutral-border rounded-full group-hover:bg-theme-primary transition-colors"></div>
      </div>

      <main className="flex-1 h-full min-w-0">
        <ChatInterface
          selectedUniqueContentIds={selectedSources.map(id => parseInt(id, 10))}
        />
      </main>
    </div>
  );
};

export default TeacherAICenter;
