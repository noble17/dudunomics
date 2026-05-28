"use client";
import { X } from "lucide-react";

interface Props {
  title: string;
  onClose?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function WidgetFrame({ title, onClose, children, className = "" }: Props) {
  return (
    <div className={`flex flex-col h-full bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-sm overflow-hidden ${className}`}>
      <div
        className="widget-drag-handle flex items-center justify-between px-3 py-1.5 border-b border-[var(--color-border)] cursor-move select-none shrink-0"
        style={{ fontSize: "11px" }}
      >
        <span className="text-[var(--color-text-secondary)] font-medium uppercase tracking-wider">
          {title}
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] p-0.5 rounded"
            onMouseDown={e => e.stopPropagation()}
          >
            <X size={12} />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-2">{children}</div>
    </div>
  );
}
