import React, { useMemo } from 'react';
import { marked } from 'marked';
import { FileContent } from '../lib/api';
import { ArrowLeft, Copy, Check, FileText, Calendar, HardDrive } from 'lucide-react';

interface NoteViewerProps {
  file: FileContent | null;
  loading: boolean;
  onBack?: () => void;
  onNavigateFile?: (path: string) => void;
}

export const NoteViewer: React.FC<NoteViewerProps> = ({
  file,
  loading,
  onBack,
  onNavigateFile,
}) => {
  const [copied, setCopied] = React.useState(false);

  const htmlContent = useMemo(() => {
    if (!file?.content) return '';
    try {
      return marked.parse(file.content, {
        gfm: true,
        breaks: true,
      }) as string;
    } catch {
      return '<p class="text-[#c55]">Failed to render markdown preview.</p>';
    }
  }, [file?.content]);

  const handleCopy = () => {
    if (file?.content) {
      navigator.clipboard.writeText(file.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Intercept wiki links or markdown links in rendered content
  const handleContentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    const link = target.closest('a');
    if (link && onNavigateFile) {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('http') && !href.startsWith('#')) {
        e.preventDefault();
        onNavigateFile(href);
      }
    }
  };

  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-[#666666] font-mono text-xs">
        <div className="w-5 h-5 border-2 border-[#404040] border-t-[#888888] animate-spin mb-3" />
        <span>Loading note contents from Obsidian vault...</span>
      </div>
    );
  }

  if (!file) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center text-[#666666] select-none font-mono">
        <FileText className="w-8 h-8 text-[#404040] mb-2" />
        <span className="text-xs text-[#888888]">No note selected</span>
        <span className="text-[11px] text-[#555555] mt-1">Select a markdown note from the file tree to read or reference</span>
      </div>
    );
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#161616]">
      {/* File Header Bar */}
      <div className="h-8 px-3 border-b border-[#262626] bg-[#1a1a1a] flex items-center justify-between shrink-0 font-mono text-xs">
        <div className="flex items-center space-x-2 truncate">
          {onBack && (
            <button
              onClick={onBack}
              title="Back to file list"
              className="p-1 text-[#888888] hover:text-[#e8e8e8] hover:bg-[#262626] transition-os md:hidden"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
            </button>
          )}
          <span className="text-[#a0a0a0] truncate font-medium">{file.name}</span>
          <span className="text-[11px] text-[#555555] hidden sm:inline truncate">
            {file.path}
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[11px] text-[#666666] shrink-0">
          <span className="flex items-center space-x-1">
            <HardDrive className="w-3 h-3" />
            <span>{formatSize(file.size)}</span>
          </span>
          <span className="hidden sm:flex items-center space-x-1">
            <Calendar className="w-3 h-3" />
            <span>{new Date(file.modified).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
          </span>
          <button
            onClick={handleCopy}
            className="p-1 text-[#888888] hover:text-[#e8e8e8] hover:bg-[#262626] transition-os flex items-center space-x-1"
            title="Copy raw markdown to clipboard"
          >
            {copied ? <Check className="w-3 h-3 text-[#4a9]" /> : <Copy className="w-3 h-3" />}
            <span className="text-[10px] hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* Note Content Area */}
      <div
        onClick={handleContentClick}
        className="flex-1 p-5 overflow-y-auto markdown-body select-text"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
};
