import { useCallback, useEffect, useState } from 'react';
import {
  listGeneratedRepos,
  listSourceProjects,
  type GeneratedRepo,
  type SourceProject,
} from '../api/client';

interface RepoTableProps {
  query: string;
  onView: (repoId: string, branch: string) => void;
  onGenerate: (repoId: string, branch: string, force: boolean) => void;
  onLoadingChange?: (loading: boolean) => void;
}

interface Row {
  repoId: string;
  description?: string;
  language?: string;
  star: number;
  branch: string;
  isGenerated: boolean;
}

export function RepoTable({ query, onView, onGenerate, onLoadingChange }: RepoTableProps) {
  const [page, setPage] = useState(1);

  const [projects, setProjects] = useState<SourceProject[]>([]);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [generated, setGenerated] = useState<Record<string, GeneratedRepo>>({});
  const [provider, setProvider] = useState<string>('');
  const [onlyGenerated, setOnlyGenerated] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the full set of already-generated repos (from /repos) once.
  const loadGenerated = useCallback(() => {
    listGeneratedRepos()
      .then((repos) => {
        const map: Record<string, GeneratedRepo> = {};
        for (const r of repos) map[r.repoId] = r;
        setGenerated(map);
      })
      .catch(() => { /* listing is best-effort */ });
  }, []);

  useEffect(() => { loadGenerated(); }, [loadGenerated]);

  // Load source projects for the browse view. Skipped in "only generated" mode,
  // which renders the full /repos list and works even if GitLab is unreachable.
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (onlyGenerated) { setLoading(false); return; }
      setLoading(true);
      setError(null);
      try {
        const res = await listSourceProjects(query, page);
        if (cancelled) return;
        setProjects(res.projects || []);
        setNextPage(res.nextPage);
        setProvider(res.provider);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load repositories');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [query, page, onlyGenerated]);

  // Reset to the first page whenever the search query changes.
  useEffect(() => { setPage(1); }, [query]);

  // Report load state up so the search box can disable itself while fetching.
  useEffect(() => { onLoadingChange?.(loading); }, [loading, onLoadingChange]);

  if (!onlyGenerated && provider && provider !== 'gitlab') {
    return (
      <p className="text-center text-sm text-gray-400 mt-8">
        仓库列表仅在后端使用 GitLab 时可用(REPO_PROVIDER=gitlab)。请使用上方搜索框。
      </p>
    );
  }

  const q = query.trim().toLowerCase();
  const matchesQuery = (...fields: (string | undefined)[]) =>
    !q || fields.some((f) => (f || '').toLowerCase().includes(q));

  // "Only generated" -> render the FULL generated list (filtered by the query
  // locally). Browse -> render the current GitLab page.
  const rows: Row[] = onlyGenerated
    ? Object.values(generated)
        .filter((r) => matchesQuery(r.repoId, r.language, r.description))
        .sort((a, b) => a.repoId.localeCompare(b.repoId))
        .map((r) => ({
          repoId: r.repoId,
          description: r.description,
          language: r.language,
          star: r.stars,
          branch: r.defaultBranch || 'main',
          isGenerated: true,
        }))
    : projects.map((p) => {
        const gen = generated[p.pathWithNamespace];
        return {
          repoId: p.pathWithNamespace,
          description: p.description,
          language: gen?.language,
          star: p.starCount,
          branch: gen?.defaultBranch || p.defaultBranch || 'main',
          isGenerated: Boolean(gen),
        };
      });

  const showPagination = !onlyGenerated;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-black">
          仓库列表{onlyGenerated ? `(已生成 ${rows.length})` : ''}
        </h2>
        <label className="flex items-center gap-2 text-sm text-gray-600 select-none">
          <input
            type="checkbox"
            checked={onlyGenerated}
            onChange={(e) => setOnlyGenerated(e.target.checked)}
          />
          只看已生成
        </label>
      </div>

      {!onlyGenerated && error && (
        <div className="rounded-md bg-red-50 p-3 border border-red-100 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}

      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left text-gray-500">
              <th className="px-4 py-3 font-medium">仓库路径</th>
              <th className="px-4 py-3 font-medium">仓库介绍</th>
              <th className="px-4 py-3 font-medium">语言</th>
              {/* <th className="px-4 py-3 font-medium">Star</th> */}
              <th className="px-4 py-3 font-medium">状态</th>
              <th className="px-4 py-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">加载中…</td></tr>
            )}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                {onlyGenerated ? '还没有已生成的仓库' : '没有仓库'}
              </td></tr>
            )}
            {!loading && rows.map((row) => (
              <tr key={row.repoId} className="hover:bg-gray-50 align-top">
                <td className="px-4 py-3 font-mono text-gray-800">{row.repoId}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate" title={row.description || ''}>
                  {row.description || '—'}
                </td>
                <td className="px-4 py-3 text-gray-600">{row.language || '—'}</td>
                {/* <td className="px-4 py-3 text-gray-600">{row.star}</td> */}
                <td className="px-4 py-3">
                  {row.isGenerated ? (
                    <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">已生成</span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">未生成</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  {row.isGenerated ? (
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => onView(row.repoId, row.branch)}
                        className="rounded-full bg-black px-4 py-1.5 text-xs font-medium text-white hover:bg-gray-800"
                      >
                        查看
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm('确定重新生成？将基于最新提交覆盖现有内容,并消耗 LLM 额度。')) {
                            onGenerate(row.repoId, row.branch, true);
                          }
                        }}
                        className="rounded-full border border-gray-300 px-4 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100"
                      >
                        生成
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => onGenerate(row.repoId, row.branch, false)}
                      className="rounded-full border border-black px-4 py-1.5 text-xs font-medium text-black hover:bg-gray-100"
                    >
                      生成
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showPagination && (
        <div className="flex items-center justify-end gap-4 mt-4 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
            className="text-gray-500 disabled:text-gray-300 hover:text-black"
          >
            ← 上一页
          </button>
          <span className="text-gray-400">第 {page} 页</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!nextPage || loading}
            className="text-gray-500 disabled:text-gray-300 hover:text-black"
          >
            下一页 →
          </button>
        </div>
      )}
    </div>
  );
}
