// frontend/src/components/common/Button.tsx
import React, { ButtonHTMLAttributes, useState, useEffect } from 'react';
import { FaCheck, FaTimes } from 'react-icons/fa';

const Spinner: React.FC = () => (
  <svg 
    className="animate-spin h-5 w-5" 
    xmlns="http://www.w3.org/2000/svg" 
    fill="none" 
    viewBox="0 0 24 24"
  >
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

type ButtonState = 'idle' | 'loading' | 'success' | 'error';

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'> {
  variant?: 'primary' | 'secondary' | 'destructive' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  buttonState?: ButtonState;
  onClick?: () => void | Promise<void>;
  idleText: React.ReactNode;
  loadingText?: React.ReactNode;
  successText?: React.ReactNode;
  errorText?: React.ReactNode;
  className?: string;
  messageDuration?: number;
}

const Button: React.FC<ButtonProps> = ({ 
  variant = 'primary', 
  size = 'md', 
  buttonState: externalState = 'idle',
  onClick,
  idleText,
  loadingText = 'Loading...',
  successText = 'Success',
  errorText = 'Error',
  className = '', 
  messageDuration = 2000,
  ...props 
}) => {
  const [internalState, setInternalState] = useState<ButtonState>(externalState);

  useEffect(() => {
    setInternalState(externalState);
  }, [externalState]);

  useEffect(() => {
    if (internalState === 'success' || internalState === 'error') {
      const timer = setTimeout(() => {
        setInternalState('idle');
      }, messageDuration);
      return () => clearTimeout(timer);
    }
  }, [internalState, messageDuration]);

  const handleClick = async () => {
    if (internalState !== 'idle' || !onClick) return;

    setInternalState('loading');
    try {
      await onClick();
      setInternalState('success');
    } catch (error) {
      console.error("Button action failed:", error);
      setInternalState('error');
    }
  };

  const baseStyles = `
    flex items-center justify-center 
    font-medium 
    rounded-default 
    shadow-default
    transition-all duration-200 ease-in-out
    focus:outline-none focus:ring-2 focus:ring-offset-2 
    disabled:opacity-50 disabled:cursor-not-allowed
    active:scale-95
    hover:shadow-md
    overflow-hidden
    whitespace-nowrap
  `;

  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }[size];

  const variantStyles = {
    primary: 'bg-theme-primary text-white hover:bg-theme-primary-hover focus:ring-theme-primary',
    secondary: 'bg-neutral-background text-neutral-text-main border border-neutral-border hover:bg-neutral-background-hover focus:ring-neutral-icon',
    destructive: 'bg-destructive text-white hover:bg-destructive-hover focus:ring-destructive',
    outline: 'bg-white text-theme-primary border border-theme-primary hover:bg-theme-background focus:ring-theme-primary',
    ghost: 'bg-transparent text-theme-primary hover:bg-theme-background focus:ring-theme-primary',
  };

  const stateStyles = {
    idle: variantStyles[variant],
    loading: `bg-theme-secondary text-white cursor-not-allowed ${variantStyles.secondary}`,
    success: 'bg-theme-success text-white focus:ring-theme-success',
    error: 'bg-destructive text-white focus:ring-destructive',
  };

  const currentStyle = stateStyles[internalState] || variantStyles[variant];

  const renderContent = () => {
    switch (internalState) {
      case 'loading':
        return (
          <span className="flex items-center gap-2">
            <Spinner />
            <span>{loadingText}</span>
          </span>
        );
      case 'success':
        return (
          <span className="flex items-center gap-2">
            <FaCheck className="w-4 h-4" />
            <span>{successText}</span>
          </span>
        );
      case 'error':
        return (
          <span className="flex items-center gap-2">
            <FaTimes className="w-4 h-4" />
            <span>{errorText}</span>
          </span>
        );
      case 'idle':
      default:
        return idleText;
    }
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles} ${currentStyle} ${className}`}
      disabled={internalState !== 'idle' || props.disabled}
      onClick={handleClick}
      {...props}
    >
      {renderContent()}
    </button>
  );
};

export default Button;