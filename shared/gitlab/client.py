"""Async GitLab API client.

Mirrors the interface of shared.github.client.GitHubClient
(fetch_repo_details / fetch_repo_tree / fetch_file / check_rate_limit) so it can
be used interchangeably by the processor. Supports gitlab.com and self-hosted
instances via a configurable base URL.

Auth: a Personal/Project Access Token sent in the PRIVATE-TOKEN header
(scopes: read_api, read_repository). Works for private projects.
"""

import os
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from urllib.parse import quote

import aiohttp

from shared.github.client import (
    GitHubAPIError,
    RepoDetails,
    TreeItem,
    TreeResult,
)


class GitLabAPIError(GitHubAPIError):
    """GitLab API error.

    Subclasses GitHubAPIError so existing ``except GitHubAPIError`` handlers
    throughout the processing pipeline catch GitLab failures unchanged.
    """
    pass


class GitLabClient:
    """Async GitLab API v4 client.

    Usage mirrors GitHubClient::

        async with GitLabClient(token="...", base_url="https://gitlab.com") as c:
            details = await c.fetch_repo_details("group", "project")
            tree = await c.fetch_repo_tree("group", "project", details.sha)
            content = await c.fetch_file("group", "project", details.sha, "path")
    """

    DEFAULT_BASE_URL = "https://gitlab.com"

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the GitLab client.

        Args:
            token: GitLab access token. Falls back to the GITLAB_TOKEN env var.
            base_url: Instance base URL (e.g. https://gitlab.example.com).
                      Falls back to GITLAB_URL env var, then gitlab.com.
        """
        self._token = token or os.getenv("GITLAB_TOKEN")
        self._base_url = (
            base_url or os.getenv("GITLAB_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self._api = f"{self._base_url}/api/v4"
        self._session: Optional[aiohttp.ClientSession] = None
        self._owns_session = False

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["PRIVATE-TOKEN"] = self._token
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._get_headers())
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._session and self._owns_session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "GitLabClient":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @staticmethod
    def _project_id(owner: str, repo: str) -> str:
        """GitLab identifies a project by URL-encoded ``namespace/project``.

        Supports nested groups when ``repo`` itself contains slashes
        (e.g. owner="group", repo="subgroup/project").
        """
        return quote(f"{owner}/{repo}", safe="")

    async def _request(self, url: str, raw: bool = False) -> Any:
        session = await self._get_session()
        # ssl=False mirrors the GitHub client and avoids cert issues on
        # self-hosted instances during local development.
        async with session.get(url, ssl=False) as response:
            if response.status != 200:
                error_text = await response.text()
                raise GitLabAPIError(response.status, error_text)
            if raw:
                return await response.text()
            return await response.json()

    async def _request_with_headers(self, url: str) -> Tuple[Any, Any]:
        session = await self._get_session()
        async with session.get(url, ssl=False) as response:
            if response.status != 200:
                error_text = await response.text()
                raise GitLabAPIError(response.status, error_text)
            return await response.json(), response.headers

    @staticmethod
    def _parse_dt(value: Optional[str]) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            # GitLab timestamps are ISO-8601 with timezone offset.
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    async def fetch_repo_details(self, owner: str, repo: str) -> RepoDetails:
        """Fetch project metadata and the default branch's HEAD commit."""
        project_id = self._project_id(owner, repo)
        project = await self._request(f"{self._api}/projects/{project_id}")

        default_branch = project.get("default_branch") or "main"

        # Resolve the HEAD commit of the default branch. Used as the ref for
        # tree/file fetches and for building blob URLs.
        commit_sha = ""
        commit_at = self._parse_dt(project.get("last_activity_at"))
        try:
            branch_data = await self._request(
                f"{self._api}/projects/{project_id}/repository/branches/"
                f"{quote(default_branch, safe='')}"
            )
            commit = branch_data.get("commit") or {}
            commit_sha = commit.get("id", "")
            commit_at = self._parse_dt(commit.get("committed_date"))
        except GitLabAPIError:
            pass

        return RepoDetails(
            owner=owner,
            name=project.get("path") or repo,
            url=project.get("web_url", f"{self._base_url}/{owner}/{repo}"),
            topics=project.get("topics") or project.get("tag_list") or [],
            language=await self._top_language(project_id),
            description=project.get("description"),
            stars=project.get("star_count", 0),
            forks=project.get("forks_count", 0),
            default_branch=default_branch,
            # Fall back to the branch name (a valid ref everywhere) if the
            # commit lookup failed.
            sha=commit_sha or default_branch,
            commit_at=commit_at,
        )

    async def _top_language(self, project_id: str) -> Optional[str]:
        """Best-effort dominant language from the /languages endpoint."""
        try:
            langs = await self._request(f"{self._api}/projects/{project_id}/languages")
            if isinstance(langs, dict) and langs:
                return max(langs, key=langs.get)
        except GitLabAPIError:
            pass
        return None

    async def fetch_repo_tree(
        self, owner: str, repo: str, sha: str, recursive: bool = True
    ) -> TreeResult:
        """Fetch the project file tree. Handles GitLab's pagination."""
        project_id = self._project_id(owner, repo)
        items: List[TreeItem] = []
        per_page = 100
        page = 1

        while True:
            url = (
                f"{self._api}/projects/{project_id}/repository/tree"
                f"?ref={quote(sha, safe='')}&per_page={per_page}&page={page}"
            )
            if recursive:
                url += "&recursive=true"

            data, headers = await self._request_with_headers(url)
            for item in data:
                items.append(
                    TreeItem(
                        path=item["path"],
                        # GitLab uses the same 'blob'/'tree' vocabulary as GitHub.
                        type=item["type"],
                        sha=item.get("id", ""),
                        size=None,  # not provided by GitLab's tree listing
                    )
                )

            next_page = headers.get("X-Next-Page")
            if next_page:
                page = int(next_page)
            elif len(data) == per_page:
                page += 1
            else:
                break
            if page > 1000:  # safety stop for pathological repos
                break

        return TreeResult(sha=sha, items=items, truncated=False)

    async def fetch_file(self, owner: str, repo: str, sha: str, path: str) -> str:
        """Fetch raw file content at a given ref."""
        project_id = self._project_id(owner, repo)
        encoded_path = quote(path, safe="")
        url = (
            f"{self._api}/projects/{project_id}/repository/files/{encoded_path}/raw"
            f"?ref={quote(sha, safe='')}"
        )
        return await self._request(url, raw=True)

    async def check_rate_limit(self) -> dict[str, Any]:
        """GitLab has no GitHub-style core rate-limit endpoint; return a stub."""
        return {"limit": 0, "remaining": 0, "reset": 0, "used": 0}
