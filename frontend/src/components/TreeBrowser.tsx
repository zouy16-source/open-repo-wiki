import { useState, useEffect } from 'react';

/**
 * Sort nodes: folders first, then files, alphabetically within each group.
 */
function sortNodes(nodes: TreeNode[]): TreeNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type === 'folder' && b.type === 'file') return -1;
    if (a.type === 'file' && b.type === 'folder') return 1;
    return a.name.localeCompare(b.name);
  });
}

/**
 * Filter nodes to only show files with summaries (folders are always shown).
 */
function filterSummarizedNodes(nodes: TreeNode[]): TreeNode[] {
  return nodes.filter((node) => {
    if (node.type === 'folder') return true;
    return node.hasSummary;
  });
}

export interface TreeNode {
  type: 'folder' | 'file';
  name: string;
  path: string;
  parentPath: string;
  hasSummary: boolean;
}

interface TreeBrowserProps {
  repoId: string;
  branch: string;
  onSelectNode: (node: TreeNode) => void;
  selectedPath?: string;
  fetchTree: (repoId: string, branch: string, path: string) => Promise<TreeNode[]>;
}

interface TreeNodeItemProps {
  node: TreeNode;
  repoId: string;
  branch: string;
  onSelectNode: (node: TreeNode) => void;
  selectedPath?: string;
  fetchTree: (repoId: string, branch: string, path: string) => Promise<TreeNode[]>;
  level: number;
  defaultOpenLevel: number;
}

function TreeNodeItem({
  node,
  repoId,
  branch,
  onSelectNode,
  selectedPath,
  fetchTree,
  level,
  defaultOpenLevel,
}: TreeNodeItemProps) {
  const isFolder = node.type === 'folder';
  const isSelected = selectedPath === node.path;

  // Root (level 0) is always open; deeper folders follow the default-open level.
  const [isOpen, setIsOpen] = useState(level === 0 ? true : level <= defaultOpenLevel);
  const [children, setChildren] = useState<TreeNode[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);

  // Lazy-load children the first time the folder is opened.
  useEffect(() => {
    if (!isFolder || !isOpen || hasLoaded) return;
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const nodes = await fetchTree(repoId, branch, node.path);
        if (cancelled) return;
        setChildren(filterSummarizedNodes(sortNodes(nodes)).filter((n) => n.path !== ''));
        setHasLoaded(true);
      } catch (err) {
        console.error('Failed to load children:', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [isFolder, isOpen, hasLoaded, repoId, branch, node.path, fetchTree]);

  const rowClass =
    `group flex items-center min-w-0 px-2 py-1 text-sm font-medium text-gray-600 ` +
    `rounded-md hover:text-gray-900 hover:bg-gray-50 ${isSelected ? 'bg-gray-100' : ''}`;

  if (!isFolder) {
    return (
      <li>
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); onSelectNode(node); }}
          title={node.name}
          className={rowClass}
        >
          {/* spacer to align file names under folder names (where the caret is) */}
          <span className="w-4 shrink-0" />
          <svg className="mr-2 h-4 w-4 shrink-0 text-gray-400 group-hover:text-gray-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
          <span className="truncate">{node.name}</span>
          {!node.hasSummary && (
            <span className="ml-2 shrink-0 text-xs text-gray-400" title="No summary available">•</span>
          )}
        </a>
      </li>
    );
  }

  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={() => onSelectNode(node)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectNode(node); }
        }}
        title={node.name}
        className={`${rowClass} cursor-pointer select-none`}
      >
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setIsOpen((o) => !o); }}
          className="mr-1 shrink-0 flex h-4 w-4 items-center justify-center text-gray-400 hover:text-gray-700"
          aria-label={isOpen ? '收起' : '展开'}
        >
          <svg
            className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-90' : ''}`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
        </button>
        <svg className="mr-2 h-4 w-4 shrink-0 text-gray-400 group-hover:text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
        </svg>
        <span className="truncate">{node.name}</span>
        {isLoading && (
          <svg className="ml-2 h-3 w-3 shrink-0 animate-spin text-gray-400" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
      </div>

      {isOpen && children.length > 0 && (
        <div className="ml-3 border-l border-gray-200 pl-2">
          <ul className="space-y-1 mt-1">
            {children.map((child) => (
              <TreeNodeItem
                key={child.path}
                node={child}
                repoId={repoId}
                branch={branch}
                onSelectNode={onSelectNode}
                selectedPath={selectedPath}
                fetchTree={fetchTree}
                level={level + 1}
                defaultOpenLevel={defaultOpenLevel}
              />
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

export function TreeBrowser({
  repoId,
  branch,
  onSelectNode,
  selectedPath,
  fetchTree,
}: TreeBrowserProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Default-open depth + a remount key, used by the expand-all / collapse-all toolbar.
  const [defaultOpenLevel, setDefaultOpenLevel] = useState(1);
  const [treeKey, setTreeKey] = useState(0);

  const repoName = repoId.split('/').pop() || repoId;

  const rootNode: TreeNode = {
    type: 'folder',
    name: repoName,
    path: '',
    parentPath: '',
    hasSummary: true,
  };

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 100);
    return () => clearTimeout(timer);
  }, [repoId, branch]);

  const handleSelectNode = (node: TreeNode) => {
    onSelectNode(node);
    setIsMobileMenuOpen(false);
  };

  const expandAll = () => { setDefaultOpenLevel(Infinity); setTreeKey((k) => k + 1); };
  const collapseAll = () => { setDefaultOpenLevel(0); setTreeKey((k) => k + 1); };

  const Toolbar = (
    <div className="flex items-center gap-3 px-2 pb-2 text-xs text-gray-400">
      <button onClick={expandAll} className="hover:text-gray-700">展开全部</button>
      <span className="text-gray-200">|</span>
      <button onClick={collapseAll} className="hover:text-gray-700">收起全部</button>
    </div>
  );

  const Spinner = (
    <div className="flex items-center justify-center py-4">
      <svg className="h-5 w-5 animate-spin text-gray-400" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>
  );

  const renderTree = (onSelect: (node: TreeNode) => void) => (
    <ul className="space-y-1">
      <TreeNodeItem
        key={`__root__-${treeKey}`}
        node={rootNode}
        repoId={repoId}
        branch={branch}
        onSelectNode={onSelect}
        selectedPath={selectedPath}
        fetchTree={fetchTree}
        level={0}
        defaultOpenLevel={defaultOpenLevel}
      />
    </ul>
  );

  return (
    <>
      {/* Mobile hamburger button */}
      <div className="lg:hidden flex items-center justify-between py-3 px-1 border-b border-gray-200">
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          aria-expanded={isMobileMenuOpen}
          aria-controls="mobile-tree-menu"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {isMobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
          <span>Files</span>
        </button>
      </div>

      {/* Mobile collapsible menu */}
      <aside
        id="mobile-tree-menu"
        className={`lg:hidden overflow-y-auto overflow-x-hidden transition-all duration-200 ease-in-out ${
          isMobileMenuOpen ? 'max-h-96 py-3 border-b border-gray-200' : 'max-h-0 overflow-hidden'
        }`}
      >
        <nav className="px-1" aria-label="Mobile Sidebar">
          {Toolbar}
          {isLoading ? Spinner : renderTree(handleSelectNode)}
        </nav>
      </aside>

      {/* Desktop sidebar - always visible on lg+ */}
      <aside className="hidden lg:block lg:col-span-3 px-2 min-w-0 h-full overflow-y-auto overflow-x-hidden py-6 border-r border-gray-200">
        <nav aria-label="Sidebar">
          {Toolbar}
          {isLoading ? Spinner : renderTree(onSelectNode)}
        </nav>
      </aside>
    </>
  );
}
