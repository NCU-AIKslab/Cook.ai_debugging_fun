// frontend/src/pages/teacher/Courses.tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { useUser } from '../../contexts/UserContext';
import API_BASE_URL from '../../config/api';
import {
    FaBell, FaChevronDown, FaChevronRight, FaClipboardCheck,
    FaFileAlt, FaPlus, FaEdit, FaTrash, FaMagic
} from 'react-icons/fa';
import Spinner from '../../components/common/Spinner';
import Modal from '../../components/common/Modal';
import Button from '../../components/common/Button';

// Type Definitions

interface CourseUnit {
    id: number;
    course_id: number;
    topic_id: number;
    name: string;
    materials?: Material[];
    assignments?: Assignment[];
}

interface CourseDetail {
    id: number;
    name: string;
    semester_name: string;
    description: string | null;
    teacher_name: string;
    units: CourseUnit[];
}

interface Announcement {
    id: number;
    course_id: number;
    title: string;
    content: string;
    author_id: number;
    created_at: string;
    updated_at: string;
}

interface Material {
    id: number;
    name: string;
    file_type: string;
    file_url: string;
    description: string | null;
    uploaded_at: string;
    uploader_id: number;
}

interface Assignment {
    id: number;
    title: string;
    due_date?: string;
}

// ==================== Component ====================

function Courses() {
    const { courseId } = useParams<{ courseId: string }>();
    const { user } = useUser(); // 取得當前登入的使用者
    const [course, setCourse] = useState<CourseDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [expandedWeeks, setExpandedWeeks] = useState<number[]>([]);

    // Modal states
    const [isAnnouncementModalOpen, setIsAnnouncementModalOpen] = useState(false);
    const [isTopicModalOpen, setIsTopicModalOpen] = useState(false);
    const [isMaterialModalOpen, setIsMaterialModalOpen] = useState(false);
    const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null);

    // Form states
    const [newAnnouncement, setNewAnnouncement] = useState({ title: '', content: '' });
    const [newChapter, setNewChapter] = useState({ chapter_number: 1, chapter_name: '', description: '' });

    // Announcements state
    const [announcements, setAnnouncements] = useState<Announcement[]>([]);

    // Mock data for testing (when API is not available)
    const mockCourses: Record<string, CourseDetail> = {
        '1': {
            id: 1,
            name: '智慧型網路服務工程',
            semester_name: '113-1',
            description: '本課程介紹智慧型網路服務的設計與實作',
            teacher_name: '楊鎮華教師',
            units: [
                { id: 1, course_id: 1, topic_id: 1, name: '課程簡介與環境設定', materials: [], assignments: [] },
                { id: 2, course_id: 1, topic_id: 2, name: '機器學習-監督式學習演算法', materials: [], assignments: [] },
                { id: 3, course_id: 1, topic_id: 3, name: '深度學習基礎', materials: [], assignments: [] },
            ]
        },
        '2': {
            id: 2,
            name: '創意學習',
            semester_name: '113-1',
            description: '創意思考與學習方法',
            teacher_name: '楊鎮華教師',
            units: [
                { id: 4, course_id: 2, topic_id: 1, name: '創意思考導論', materials: [], assignments: [] },
            ]
        }
    };

    // Fetch course detail and announcements
    useEffect(() => {
        const fetchCourseDetail = async () => {
            if (!courseId) return;

            try {
                setIsLoading(true);
                const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}`);

                if (!response.ok) {
                    throw new Error('API 無法連線');
                }

                const data = await response.json();
                setCourse(data);

                if (data.units && data.units.length > 0) {
                    setExpandedWeeks([data.units[0].topic_id]);
                }
            } catch (err) {
                // Fallback to mock data for testing
                console.warn('API 無法連線，使用測試資料:', err);
                const mockCourse = mockCourses[courseId];
                if (mockCourse) {
                    setCourse(mockCourse);
                    if (mockCourse.units.length > 0) {
                        setExpandedWeeks([mockCourse.units[0].topic_id]);
                    }
                    setError(null); // Clear error since we have mock data
                } else {
                    setError('課程不存在');
                }
            } finally {
                setIsLoading(false);
            }
        };

        const fetchAnnouncements = async () => {
            if (!courseId) return;

            try {
                const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/announcements`);
                if (response.ok) {
                    const data = await response.json();
                    setAnnouncements(data);
                }
            } catch (err) {
                console.warn('無法載入公告:', err);
            }
        };

        fetchCourseDetail();
        fetchAnnouncements();
    }, [courseId]);

    const toggleWeek = (week: number) => {
        setExpandedWeeks(prev =>
            prev.includes(week)
                ? prev.filter(w => w !== week)
                : [...prev, week]
        );
    };

    // ==================== Handler Functions ====================

    const handleAddAnnouncement = async () => {
        if (!courseId || !user) return;

        try {
            const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/announcements`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: newAnnouncement.title,
                    content: newAnnouncement.content,
                    author_id: user.user_id
                })
            });

            if (response.ok) {
                const newItem = await response.json();
                setAnnouncements([newItem, ...announcements]);
                setNewAnnouncement({ title: '', content: '' });
                setIsAnnouncementModalOpen(false);
            } else {
                console.error('新增公告失敗');
            }
        } catch (err) {
            console.error('新增公告錯誤:', err);
        }
    };

    const handleDeleteAnnouncement = async (id: number) => {
        if (!courseId) return;

        try {
            const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/announcements/${id}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                setAnnouncements(announcements.filter(a => a.id !== id));
            } else {
                console.error('刪除公告失敗');
            }
        } catch (err) {
            console.error('刪除公告錯誤:', err);
        }
    };

    const handleAddChapter = async () => {
        if (!course || !courseId) return;

        try {
            const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/units`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_id: newChapter.chapter_number,
                    name: newChapter.chapter_name,
                    description: newChapter.description
                })
            });

            if (response.ok) {
                const newUnit = await response.json();
                setCourse({
                    ...course,
                    units: [...course.units, newUnit].sort((a, b) => a.topic_id - b.topic_id)
                });
                setNewChapter({ chapter_number: course.units.length + 2, chapter_name: '', description: '' });
                setIsTopicModalOpen(false);
            } else {
                console.error('新增章節失敗');
            }
        } catch (err) {
            console.error('新增章節錯誤:', err);
        }
    };

    const handleDeleteTopic = async (unitId: number) => {
        if (!course || !courseId) return;

        try {
            const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/units/${unitId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                setCourse({
                    ...course,
                    units: course.units.filter(u => u.id !== unitId)
                });
            } else {
                console.error('刪除章節失敗');
            }
        } catch (err) {
            console.error('刪除章節錯誤:', err);
        }
    };

    const openMaterialModal = (unitId: number) => {
        setSelectedUnitId(unitId);
        setIsMaterialModalOpen(true);
        console.log('Opening material modal for unit:', unitId);
    };

    // ==================== Render ====================

    if (isLoading) {
        return (
            <div className="py-12 flex justify-center">
                <Spinner />
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-destructive-light border border-destructive text-destructive px-4 py-3 rounded-lg mx-6 mt-6">
                {error}
            </div>
        );
    }

    if (!course) {
        return (
            <div className="text-center py-12 text-neutral-text-tertiary">
                課程不存在
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* ==================== 公告區塊 ==================== */}
            <div className="bg-white rounded-xl border border-neutral-border p-6 shadow-card">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <FaBell className="text-theme-primary" size={16} />
                        <h2 className="text-base font-semibold text-neutral-text-main">最新公告</h2>
                    </div>
                    <button
                        onClick={() => setIsAnnouncementModalOpen(true)}
                        className="flex items-center gap-1.5 text-sm text-theme-primary hover:text-theme-primary-hover font-medium transition-colors"
                    >
                        <FaPlus size={12} />
                        新增公告
                    </button>
                </div>

                {announcements.length > 0 ? (
                    <div className="space-y-3">
                        {announcements.map((announcement) => (
                            <div
                                key={announcement.id}
                                className="bg-theme-primary-light rounded-lg p-4 border border-theme-border-light flex items-center justify-between gap-4"
                            >
                                <div className="flex items-start gap-3 flex-1">
                                    <div className="w-2 h-2 rounded-full bg-theme-primary flex-shrink-0 mt-1.5"></div>
                                    <div className="flex-1">
                                        <p className="font-medium text-neutral-text-main mb-1">{announcement.title}</p>
                                        {announcement.content && (
                                            <div className="text-sm text-neutral-text-secondary prose prose-sm max-w-none">
                                                <ReactMarkdown>{announcement.content}</ReactMarkdown>
                                            </div>
                                        )}
                                        <p className="text-theme-primary text-xs mt-2">{new Date(announcement.created_at).toLocaleString('zh-TW')}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button className="p-2 text-neutral-icon hover:text-theme-primary transition-colors">
                                        <FaEdit size={14} />
                                    </button>
                                    <button
                                        onClick={() => handleDeleteAnnouncement(announcement.id)}
                                        className="p-2 text-neutral-icon hover:text-destructive transition-colors"
                                    >
                                        <FaTrash size={14} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="text-neutral-text-tertiary italic">目前沒有公告</p>
                )}
            </div>

            {/* ==================== 課程內容標題 ==================== */}
            <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-neutral-text-main">課程內容</h2>
                <button
                    onClick={() => {
                        setNewChapter({ chapter_number: course.units.length + 1, chapter_name: '', description: '' });
                        setIsTopicModalOpen(true);
                    }}
                    className="btn-primary flex items-center gap-2 text-sm"
                >
                    <FaPlus size={12} />
                    新增章節
                </button>
            </div>

            {/* ==================== 週次列表 ==================== */}
            {course.units.length === 0 ? (
                <div className="text-center py-12 text-neutral-text-tertiary bg-white rounded-xl border border-neutral-border">
                    此課程尚未設定章節，請點擊「新增章節」建立第一個單元
                </div>
            ) : (
                <div className="space-y-3">
                    {course.units.map((unit) => {
                        const isExpanded = expandedWeeks.includes(unit.topic_id);

                        return (
                            <div
                                key={unit.id}
                                className={`bg-white rounded-xl transition-all duration-200 ${isExpanded
                                    ? 'border-2 border-theme-primary shadow-card-hover'
                                    : 'border border-neutral-border hover:border-neutral-icon shadow-card'
                                    }`}
                            >
                                {/* 週次標題列 */}
                                <div className="px-6 py-5 flex items-center justify-between">
                                    <div
                                        className="flex items-center gap-3 flex-1 cursor-pointer select-none"
                                        onClick={() => toggleWeek(unit.topic_id)}
                                    >
                                        {isExpanded ? (
                                            <FaChevronDown className="text-neutral-text-tertiary" size={14} />
                                        ) : (
                                            <FaChevronRight className="text-neutral-text-tertiary" size={14} />
                                        )}
                                        <div className={`text-base font-semibold ${isExpanded ? 'text-theme-primary' : 'text-neutral-text-main'}`}>
                                            章節 {unit.topic_id}: {unit.name}
                                        </div>
                                    </div>

                                    {/* 教師操作按鈕 */}
                                    <div className="flex items-center gap-2">
                                        <button className="p-2 text-neutral-icon hover:text-theme-primary transition-colors" title="編輯">
                                            <FaEdit size={14} />
                                        </button>
                                        <button
                                            onClick={() => handleDeleteTopic(unit.id)}
                                            className="p-2 text-neutral-icon hover:text-destructive transition-colors"
                                            title="刪除"
                                        >
                                            <FaTrash size={14} />
                                        </button>
                                    </div>
                                </div>

                                {/* 展開的內容區塊 - 雙欄設計 */}
                                {isExpanded && (
                                    <div className="px-6 pb-6 border-t border-neutral-border pt-5">
                                        {/* 學習知識點 + 統計標籤 */}
                                        <div className="flex items-center justify-between mb-5">
                                            <p className="text-neutral-text-secondary text-sm">
                                                學習知識點：{unit.name}相關內容
                                            </p>
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">課前預習</span>
                                                <span className="text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-medium">課後複習</span>
                                            </div>
                                        </div>

                                        {/* 雙欄佈局 */}
                                        <div className="grid grid-cols-2 gap-6">
                                            {/* 左欄：教材 */}
                                            <div className="bg-gray-50 rounded-xl p-4">
                                                <div className="flex items-center justify-between mb-3">
                                                    <div className="flex items-center gap-2">
                                                        <FaFileAlt size={16} className="text-blue-600" />
                                                        <h4 className="text-base font-semibold text-neutral-text-main">教材</h4>
                                                        <span className="text-xs text-neutral-text-tertiary">({unit.materials?.length || 0})</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <button
                                                            onClick={() => openMaterialModal(unit.id)}
                                                            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100 rounded-lg transition-colors font-medium"
                                                        >
                                                            <FaPlus size={10} /> 新增教材
                                                        </button>
                                                        <button className="flex items-center gap-1 px-2 py-1 text-xs text-teal-700 hover:bg-teal-100 rounded-lg transition-colors font-medium">
                                                            <FaMagic size={10} /> AI生成教材
                                                        </button>
                                                    </div>
                                                </div>

                                                {(!unit.materials || unit.materials.length === 0) ? (
                                                    <div className="text-neutral-text-tertiary text-sm italic py-4 text-center">
                                                        尚未新增教材
                                                    </div>
                                                ) : (
                                                    <ul className="space-y-1.5">
                                                        {unit.materials.map((material, idx) => (
                                                            <li key={material.id} className="flex items-center justify-between py-1.5 px-2 hover:bg-white rounded-lg group transition-colors">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-xs text-neutral-text-tertiary w-4">{idx + 1}.</span>
                                                                    <span className="text-sm text-neutral-text-main">{material.name}</span>
                                                                </div>
                                                                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                                                    <button className="p-1 text-neutral-icon hover:text-blue-600"><FaEdit size={11} /></button>
                                                                    <button className="p-1 text-neutral-icon hover:text-destructive"><FaTrash size={11} /></button>
                                                                </div>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>

                                            {/* 右欄：作業 */}
                                            <div className="bg-gray-50 rounded-xl p-4">
                                                <div className="flex items-center justify-between mb-3">
                                                    <div className="flex items-center gap-2">
                                                        <FaClipboardCheck size={16} className="text-teal-600" />
                                                        <h4 className="text-base font-semibold text-neutral-text-main">作業</h4>
                                                        <span className="text-xs text-neutral-text-tertiary">({unit.assignments?.length || 0})</span>
                                                    </div>
                                                    <div className="flex items-center gap-1">
                                                        <button className="flex items-center gap-1 px-2 py-1 text-xs text-teal-700 hover:bg-teal-100 rounded-lg transition-colors font-medium">
                                                            <FaPlus size={10} /> 新增作業
                                                        </button>
                                                        <button className="flex items-center gap-1 px-2 py-1 text-xs text-purple-700 hover:bg-purple-100 rounded-lg transition-colors font-medium">
                                                            <FaMagic size={10} /> AI生成習題
                                                        </button>
                                                    </div>
                                                </div>

                                                {(!unit.assignments || unit.assignments.length === 0) ? (
                                                    <div className="text-neutral-text-tertiary text-sm italic py-4 text-center">
                                                        尚未新增作業
                                                    </div>
                                                ) : (
                                                    <ul className="space-y-1.5">
                                                        {unit.assignments.map((assignment, idx) => (
                                                            <li key={assignment.id} className="flex items-center justify-between py-1.5 px-2 hover:bg-white rounded-lg group transition-colors">
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-xs text-neutral-text-tertiary w-4">{idx + 1}.</span>
                                                                    <span className="text-sm text-neutral-text-main">{assignment.title}</span>
                                                                </div>
                                                                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                                                    <button className="p-1 text-neutral-icon hover:text-teal-600"><FaEdit size={11} /></button>
                                                                    <button className="p-1 text-neutral-icon hover:text-destructive"><FaTrash size={11} /></button>
                                                                </div>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* ==================== Modals ==================== */}

            {/* 新增公告 Modal */}
            <Modal
                isOpen={isAnnouncementModalOpen}
                onClose={() => setIsAnnouncementModalOpen(false)}
                title="新增公告"
            >
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-neutral-text-main mb-1">標題</label>
                        <input
                            type="text"
                            value={newAnnouncement.title}
                            onChange={(e) => setNewAnnouncement({ ...newAnnouncement, title: e.target.value })}
                            className="w-full px-4 py-2 border border-neutral-border rounded-lg focus:ring-2 focus:ring-theme-ring focus:border-theme-primary"
                            placeholder="請輸入公告標題"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-neutral-text-main mb-1">內容</label>
                        <textarea
                            value={newAnnouncement.content}
                            onChange={(e) => setNewAnnouncement({ ...newAnnouncement, content: e.target.value })}
                            className="w-full px-4 py-2 border border-neutral-border rounded-lg focus:ring-2 focus:ring-theme-ring focus:border-theme-primary h-24"
                            placeholder="請輸入公告內容（選填）"
                        />
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                        <Button variant="secondary" onClick={() => setIsAnnouncementModalOpen(false)} idleText="取消" />
                        <Button
                            variant="primary"
                            onClick={handleAddAnnouncement}
                            idleText="新增"
                            disabled={!newAnnouncement.title.trim()}
                        />
                    </div>
                </div>
            </Modal>

            {/* 新增章節 Modal */}
            <Modal
                isOpen={isTopicModalOpen}
                onClose={() => setIsTopicModalOpen(false)}
                title="新增章節"
            >
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-neutral-text-main mb-1">章節編號</label>
                        <input
                            type="number"
                            min="1"
                            value={newChapter.chapter_number}
                            onChange={(e) => setNewChapter({ ...newChapter, chapter_number: parseInt(e.target.value) || 1 })}
                            className="w-full px-4 py-2 border border-neutral-border rounded-lg focus:ring-2 focus:ring-theme-ring focus:border-theme-primary"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-neutral-text-main mb-1">章節名稱</label>
                        <input
                            type="text"
                            value={newChapter.chapter_name}
                            onChange={(e) => setNewChapter({ ...newChapter, chapter_name: e.target.value })}
                            className="w-full px-4 py-2 border border-neutral-border rounded-lg focus:ring-2 focus:ring-theme-ring focus:border-theme-primary"
                            placeholder="例如：機器學習-監督式學習演算法"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-neutral-text-main mb-1">章節說明 <span className="text-neutral-text-tertiary">(支援 Markdown)</span></label>
                        <textarea
                            value={newChapter.description}
                            onChange={(e) => setNewChapter({ ...newChapter, description: e.target.value })}
                            className="w-full px-4 py-2 border border-neutral-border rounded-lg focus:ring-2 focus:ring-theme-ring focus:border-theme-primary h-24"
                            placeholder="輸入學習知識點或章節說明..."
                        />
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                        <Button variant="secondary" onClick={() => setIsTopicModalOpen(false)} idleText="取消" />
                        <Button
                            variant="primary"
                            onClick={handleAddChapter}
                            idleText="新增"
                            disabled={!newChapter.chapter_name.trim()}
                        />
                    </div>
                </div>
            </Modal>

            {/* 新增教材 Modal */}
            <Modal
                isOpen={isMaterialModalOpen}
                onClose={() => setIsMaterialModalOpen(false)}
                title="新增教材"
            >
                <div className="space-y-4">
                    <p className="text-neutral-text-secondary text-sm">
                        選擇要新增到此 Topic 的教材方式
                    </p>
                    <div className="grid grid-cols-2 gap-4">
                        <button className="p-4 border border-neutral-border rounded-lg hover:border-theme-primary hover:bg-theme-primary-light transition-colors text-center">
                            <FaFileAlt className="mx-auto mb-2 text-theme-primary" size={24} />
                            <span className="font-medium text-neutral-text-main">上傳檔案</span>
                        </button>
                        <button className="p-4 border border-neutral-border rounded-lg hover:border-theme-accent hover:bg-theme-accent-light transition-colors text-center">
                            <FaMagic className="mx-auto mb-2 text-theme-accent" size={24} />
                            <span className="font-medium text-neutral-text-main">AI 生成</span>
                        </button>
                    </div>
                    <div className="flex justify-end pt-2">
                        <Button variant="secondary" onClick={() => setIsMaterialModalOpen(false)} idleText="取消" />
                    </div>
                </div>
            </Modal>
        </div>
    );
}

export default Courses;
