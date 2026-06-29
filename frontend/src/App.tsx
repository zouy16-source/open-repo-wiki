/**
 * Main App component with routing.
 *
 * Routes:
 * - / (Home): RepoForm for submitting repositories
 * - /processing/:jobId: ProgressView for tracking job progress
 * - /:owner/:repo: TreeBrowser and PageViewer for browsing documentation
 *
 * Requirements: 8.1, 8.2, 8.3
 */

import { BrowserRouter, Routes, Route, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useState, useCallback, useEffect } from 'react';
import { RepoTable } from './components/RepoTable';
import { ProgressView } from './components/ProgressView';
import { TreeBrowser, type TreeNode } from './components/TreeBrowser';
import { PageViewer } from './components/PageViewer';
import { Breadcrumb } from './components/Breadcrumb';
import { createJob, getJob, getTree, getPage } from './api/client';
import './App.css';



/**
 * Home page with repository submission form.
 * Requirements: 8.1
 */
function HomePage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);

  const handleGenerate = async (repoId: string, branch: string, force: boolean = false) => {
    setError(null);

    const branchParam = branch || 'main';
    // owner = first segment, repo = the rest (supports GitLab nested groups)
    const [owner, ...rest] = repoId.split('/');
    const repo = rest.join('/');
    try {
      const result = await createJob(owner, repo, branch, force);

      if (result.status === 'completed') {
        // Already generated - go directly to result page
        navigate(`/${repoId}?branch=${encodeURIComponent(branchParam)}`);
      } else {
        // New / regenerating job - go to processing page
        navigate(`/processing/${result.jobId}?repoId=${encodeURIComponent(repoId)}&branch=${encodeURIComponent(branchParam)}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
    }
  };

  const handleView = useCallback((repoId: string, branch: string) => {
    navigate(`/${repoId}?branch=${encodeURIComponent(branch || 'main')}`);
  }, [navigate]);

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-2xl mx-auto px-4 pt-16 text-center">
        <h1 className="text-3xl font-bold tracking-tight text-black sm:text-4xl mb-2">
          Open Repo Wiki
        </h1>
        <p className="text-lg text-gray-500 mb-8">为任意 Git 仓库即时生成中文文档。</p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (searching) return;            // prevent duplicate submits while searching
            setQuery(searchInput.trim());
          }}
          className="relative"
        >
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="搜索仓库(名称、路径或介绍)…"
            disabled={searching}
            className="w-full rounded-full border border-gray-300 py-4 pl-6 pr-16 text-lg outline-none focus:border-black focus:ring-0 disabled:bg-gray-50"
            style={{ boxShadow: '0 0 15px rgba(0,0,0,0.1)' }}
          />
          <button
            type="submit"
            disabled={searching}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-11 h-11 flex items-center justify-center rounded-full bg-black text-white hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed"
            aria-label="搜索"
          >
            {searching ? (
              <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
              </svg>
            )}
          </button>
        </form>
      </div>

      <div className="max-w-7xl mx-auto px-4 pt-10 pb-20">
        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 border border-red-100 text-sm text-red-700">
            {error}
          </div>
        )}
        <RepoTable query={query} onView={handleView} onGenerate={handleGenerate} onLoadingChange={setSearching} />
      </div>
    </div>
  );
}

/**
 * Processing page showing job progress.
 * Requirements: 8.2
 */
function ProcessingPage() {
  const navigate = useNavigate();
  const { jobId } = useParams<{ jobId: string }>();
  const [searchParams] = useSearchParams();

  // repoId may be nested (group/subgroup/project); derive owner/repo for display.
  const repoId = searchParams.get('repoId') || '';
  const segments = repoId.split('/').filter(Boolean);
  const repo = segments[segments.length - 1] || '';
  const owner = segments.slice(0, -1).join('/');

  const handleComplete = useCallback((completedRepoId: string, branch: string) => {
    navigate(`/${completedRepoId}?branch=${encodeURIComponent(branch)}`);
  }, [navigate]);

  const handleError = useCallback((error: string) => {
    console.error('Job failed:', error);
    // Stay on page to show error state
  }, []);

  if (!jobId) {
    navigate('/');
    return null;
  }

  return (
    <ProgressView
      jobId={jobId}
      owner={owner}
      repo={repo}
      onComplete={handleComplete}
      onError={handleError}
      fetchJob={getJob}
    />
  );
}


/**
 * Repository browser page with tree navigation and page viewer.
 * Requirements: 8.3
 */
function RepoPage() {
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  // Route is "/:owner/*", so the repo id can be any depth (GitLab nested groups).
  const ownerSeg = params.owner || '';
  const restSeg = params['*'] || '';
  const repoId = restSeg ? `${ownerSeg}/${restSeg}` : ownerSeg;

  const segments = repoId.split('/').filter(Boolean);
  const repoName = segments[segments.length - 1] || '';
  const ownerPath = segments.slice(0, -1).join('/');

  const branch = searchParams.get('branch') || 'main';
  const currentPath = searchParams.get('path') || '';

  // Create a synthetic root node for initial display
  const createRootNode = useCallback((): TreeNode | null => {
    if (!repoName) return null;
    return {
      type: 'folder',
      name: repoName,
      path: '',
      parentPath: '',
      hasSummary: true
    };
  }, [repoName]);

  // Initialize with root node if no path is specified
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(() => {
    // If there's no path in URL, start with root node
    if (!currentPath) {
      return createRootNode();
    }
    return null;
  });
  const [repoSummary] = useState<string | undefined>(undefined);

  // Update selected node when URL path changes
  useEffect(() => {
    if (!currentPath && !selectedNode) {
      setSelectedNode(createRootNode());
    }
  }, [currentPath, selectedNode, createRootNode]);

  const handleSelectNode = useCallback((node: TreeNode) => {
    setSelectedNode(node);
    setSearchParams((prev) => {
      prev.set('path', node.path);
      return prev;
    });
  }, [setSearchParams]);

  const handleNavigate = useCallback((path: string) => {
    setSearchParams((prev) => {
      prev.set('path', path);
      return prev;
    });
    setSelectedNode(null);
  }, [setSearchParams]);

  const handleGoToRoot = useCallback(() => {
    setSearchParams((prev) => {
      prev.delete('path');
      return prev;
    });
    // Set root node as selected when going to root
    setSelectedNode(createRootNode());
  }, [setSearchParams, createRootNode]);

  const handleExpandRequest = useCallback((node: TreeNode) => {
    console.log('Expand request for:', node.path);
  }, []);

  if (!repoId || !repoId.includes('/')) {
    navigate('/');
    return null;
  }

  return (
    <div className="h-screen bg-white flex flex-col overflow-hidden">
      <Breadcrumb
        owner={ownerPath}
        repo={repoName}
        currentPath={currentPath}
        onNavigate={handleNavigate}
        onGoToRoot={handleGoToRoot}
      />
      <div className="flex-1 max-w-full mx-auto w-full overflow-hidden">
        <div className="flex flex-col lg:grid lg:grid-cols-12 lg:gap-8 h-full overflow-hidden">
          <TreeBrowser
            repoId={repoId}
            branch={branch}
            onSelectNode={handleSelectNode}
            selectedPath={selectedNode?.path || currentPath}
            fetchTree={getTree}
          />
          <PageViewer
            repoId={repoId}
            branch={branch}
            selectedNode={selectedNode}
            repoSummary={repoSummary}
            fetchPage={getPage}
            onExpandRequest={handleExpandRequest}
          />
        </div>
      </div>
    </div>
  );
}



/**
 * Main App component with router configuration.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/processing/:jobId" element={<ProcessingPage />} />
        <Route path="/:owner/*" element={<RepoPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
