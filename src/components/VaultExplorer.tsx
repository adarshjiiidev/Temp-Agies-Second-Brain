import React, { useState, useEffect, useCallback } from 'react';
import { Panel } from './Panel';
import { NoteViewer } from './NoteViewer';
import { ObsidianGraph } from './ObsidianGraph';
import { api, MemoryFile, FileContent } from '../lib/api';
import { useOS } from '../lib/store';
import {
  FolderTree,
  Folder,
  FolderOpen,
  FileText,
  FileCode,
  Search,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Share2,
} from 'lucide-react';

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children?: TreeNode[];
  size?: number;
}

export const VaultExplorer: React.FC = () => {
  const { targetVaultFile, setTargetVaultFile } = useOS();
  const [viewMode, setViewMode] = useState<'tree' | 'graph'>('tree');
  const [allFiles, setAllFiles] = useState<MemoryFile[]>([]);
  const [fileTree, setFileTree] = useState<TreeNode[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    'memory': true,
    'memory/1-Projects': true,
    'memory/MOCs': true,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [loadingVault, setLoadingVault] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Build a tree from flat memory files
  const buildTree = useCallback((files: MemoryFile[]): TreeNode[] => {
    const root: Record<string, unknown> = {};

    files.forEach((file) => {
      const parts = file.path.split('/');
      let current: Record<string, unknown> = root;

      parts.forEach((part, index) => {
        const isFile = index === parts.length - 1;
        const currentPath = parts.slice(0, index + 1).join('/');

        if (!current[part]) {
          current[part] = {
            name: part,
            path: currentPath,
            isDir: !isFile,
            size: isFile ? file.size : undefined,
            children: isFile ? undefined : {},
          };
        }
        if (!isFile) {
          current = (current[part] as { children: Record<string, unknown> }).children;
        }
      });
    });

    const convertToNodeArray = (obj: Record<string, unknown>): TreeNode[] => {
      return Object.values(obj)
        .map((item: any) => {
          if (item.isDir) {
            return {
              ...item,
              children: convertToNodeArray(item.children || {}).sort((a, b) => {
                if (a.isDir && !b.isDir) return -1;
                if (!a.isDir && b.isDir) return 1;
                return a.name.localeCompare(b.name);
              }),
            };
          }
          return item;
        })
        .sort((a, b) => {
          if (a.isDir && !b.isDir) return -1;
          if (!a.isDir && b.isDir) return 1;
          return a.name.localeCompare(b.name);
        });
    };

    return convertToNodeArray(root);
  }, []);

  const loadVaultFiles = useCallback(async () => {
    setLoadingVault(true);
    setErrorMsg(null);
    try {
      const files = await api.getMemoryFiles();
      setAllFiles(files);
      const tree = buildTree(files);
      setFileTree(tree);

      // Default select the first prominent project or MOC note
      if (!selectedFilePath && files.length > 0) {
        const defaultNote = files.find(
          (f) => f.path.includes('1-Projects') || f.path.includes('MOCs') || f.path.endsWith('.md')
        ) || files[0];
        if (defaultNote) {
          loadFile(defaultNote.path);
        }
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load vault');
    } finally {
      setLoadingVault(false);
    }
  }, [buildTree, selectedFilePath]);

  useEffect(() => {
    loadVaultFiles();
  }, []);

  const loadFile = async (path: string) => {
    setSelectedFilePath(path);
    setLoadingFile(true);
    try {
      const data = await api.getFile(path);
      setFileContent(data);
    } catch {
      setFileContent({
        name: path.split('/').pop() || 'note.md',
        path,
        content: `# Error\nCould not load file \`${path}\`. It may have been moved or removed.`,
        size: 0,
        modified: new Date().toISOString(),
      });
    } finally {
      setLoadingFile(false);
    }
  };

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [path]: !prev[path],
    }));
  };

  // Filtered files for search
  const filteredFiles = searchQuery
    ? allFiles.filter(
        (f) =>
          f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          f.path.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : null;

  const renderTree = (nodes: TreeNode[], depth = 0) => {
    return nodes.map((node) => {
      const isExpanded = !!expandedFolders[node.path];
      const isSelected = selectedFilePath === node.path;

      if (node.isDir) {
        return (
          <div key={node.path} className="select-none">
            <button
              onClick={() => toggleFolder(node.path)}
              className="w-full text-left px-2 py-1 flex items-center space-x-1.5 hover:bg-[#222222] transition-os text-[#a0a0a0] hover:text-[#e8e8e8] text-xs font-mono"
              style={{ paddingLeft: `${Math.max(6, depth * 14 + 6)}px` }}
            >
              <span className="text-[#666666]">
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </span>
              <span className="text-[#888888]">
                {isExpanded ? <FolderOpen className="w-3.5 h-3.5 text-[#a0a0a0]" /> : <Folder className="w-3.5 h-3.5" />}
              </span>
              <span className="truncate font-medium">{node.name}</span>
            </button>
            {isExpanded && node.children && (
              <div>{renderTree(node.children, depth + 1)}</div>
            )}
          </div>
        );
      }

      return (
        <button
          key={node.path}
          onClick={() => loadFile(node.path)}
          className={`w-full text-left px-2 py-1 flex items-center space-x-1.5 transition-os text-xs font-mono truncate ${
            isSelected
              ? 'bg-[#282828] text-[#e8e8e8] font-medium border-l-2 border-[#888888]'
              : 'hover:bg-[#202020] text-[#888888] hover:text-[#a0a0a0]'
          }`}
          style={{ paddingLeft: `${Math.max(16, depth * 14 + 16)}px` }}
        >
          {node.name.endsWith('.json') ? (
            <FileCode className="w-3.5 h-3.5 text-[#888888] shrink-0" />
          ) : (
            <FileText className="w-3.5 h-3.5 text-[#777777] shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </button>
      );
    });
  };

  useEffect(() => {
    if (targetVaultFile) {
      loadFile(targetVaultFile);
      setViewMode('tree');
      setTargetVaultFile(null);
    }
  }, [targetVaultFile, setTargetVaultFile]);

  return (
    <Panel
      id="vault"
      title="Vault Explorer"
      icon={<FolderTree className="w-3.5 h-3.5 text-[#a0a0a0]" />}
      tag="Obsidian"
      headerRight={
        <div className="flex items-center space-x-1">
          <div className="flex items-center bg-[#222222] p-0.5 border border-[#333333] mr-1">
            <button
              onClick={() => setViewMode('tree')}
              title="Tree View"
              className={`px-1.5 py-0.5 text-[10px] font-mono transition-os flex items-center space-x-1 ${
                viewMode === 'tree' ? 'bg-[#333333] text-white font-medium' : 'text-[#888888] hover:text-white'
              }`}
            >
              <FolderTree className="w-2.5 h-2.5" />
              <span>Tree</span>
            </button>
            <button
              onClick={() => setViewMode('graph')}
              title="Knowledge Graph View"
              className={`px-1.5 py-0.5 text-[10px] font-mono transition-os flex items-center space-x-1 ${
                viewMode === 'graph' ? 'bg-[#333333] text-white font-medium' : 'text-[#888888] hover:text-white'
              }`}
            >
              <Share2 className="w-2.5 h-2.5 text-[#38bdf8]" />
              <span>Graph</span>
            </button>
          </div>
          <button
            onClick={loadVaultFiles}
            title="Refresh Vault Tree"
            className="w-5 h-5 flex items-center justify-center text-[#888888] hover:text-[#e8e8e8] hover:bg-[#2a2a2a] transition-os"
          >
            <RefreshCw className={`w-3 h-3 ${loadingVault ? 'animate-spin text-[#4a9]' : ''}`} />
          </button>
        </div>
      }
    >
      {viewMode === 'graph' ? (
        <ObsidianGraph isEmbedded={true} />
      ) : (
      <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden bg-[#141414]">
        {/* Left Sub-panel: File Tree (28% width on desktop) */}
        <div className="w-full md:w-64 lg:w-72 border-b md:border-b-0 md:border-r border-[#262626] flex flex-col bg-[#181818] shrink-0 h-48 md:h-full">
          {/* Tree Header & Search */}
          <div className="p-2 border-b border-[#262626] bg-[#161616]">
            <div className="relative">
              <Search className="w-3 h-3 text-[#666666] absolute left-2 top-2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter vault files..."
                className="w-full h-7 pl-7 pr-2 bg-[#121212] border border-[#2a2a2a] focus:border-[#404040] text-[#e8e8e8] text-xs font-mono outline-none placeholder-[#555555]"
              />
            </div>
          </div>

          {/* Folder & File Tree list */}
          <div className="flex-1 overflow-y-auto py-1">
            {errorMsg ? (
              <div className="p-4 text-xs font-mono text-[#c55]">{errorMsg}</div>
            ) : filteredFiles ? (
              // Flat search view
              <div className="p-1 space-y-0.5">
                <div className="text-[10px] text-[#666666] px-2 py-1 uppercase font-mono">
                  Search Results ({filteredFiles.length})
                </div>
                {filteredFiles.map((file) => (
                  <button
                    key={file.path}
                    onClick={() => loadFile(file.path)}
                    className={`w-full text-left px-2 py-1 flex items-center space-x-2 transition-os text-xs font-mono truncate ${
                      selectedFilePath === file.path
                        ? 'bg-[#282828] text-[#e8e8e8]'
                        : 'hover:bg-[#202020] text-[#888888] hover:text-[#e8e8e8]'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5 text-[#777777] shrink-0" />
                    <div className="truncate">
                      <div className="text-xs truncate">{file.name}</div>
                      <div className="text-[10px] text-[#555555] truncate">{file.path}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              // Nested directory tree view
              renderTree(fileTree)
            )}
          </div>

          {/* Vault Footer status */}
          <div className="h-6 px-2.5 border-t border-[#262626] bg-[#141414] flex items-center justify-between text-[11px] font-mono text-[#666666]">
            <span>PARA Vault</span>
            <span>{allFiles.length} files</span>
          </div>
        </div>

        {/* Right Sub-panel: Note Viewer */}
        <div className="flex-1 h-full overflow-hidden">
          <NoteViewer
            file={fileContent}
            loading={loadingFile}
            onNavigateFile={(path) => loadFile(path)}
          />
        </div>
      </div>
      )}
    </Panel>
  );
};
