import React from 'react';

interface StatusBadgeProps {
    status: 'success' | 'warning' | 'danger' | 'info';
    children: React.ReactNode;
    className?: string;
}

const statusStyles = {
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
    info: 'badge-info',
};

/**
 * LangSmith-style pill badge for status display
 */
function StatusBadge({ status, children, className = '' }: StatusBadgeProps) {
    return (
        <span className={`badge ${statusStyles[status]} ${className}`}>
            {children}
        </span>
    );
}

export default StatusBadge;
