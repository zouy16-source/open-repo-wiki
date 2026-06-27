"""Repository source provider selection.

Picks the right read client (GitHub or GitLab) and the matching blob-URL
pattern (used in LLM prompts so generated code links point at the right host).
"""

from typing import Optional, Union

from shared.github.client import GitHubClient
from shared.gitlab.client import GitLabClient
from services.processor.llm.prompts import (
    GITHUB_FILE_URL_PATTERN,
    gitlab_file_url_pattern,
)

GITHUB = "github"
GITLAB = "gitlab"

SourceClient = Union[GitHubClient, GitLabClient]


def normalize_provider(provider: Optional[str]) -> str:
    return (provider or GITHUB).strip().lower()


def create_source_client(
    provider: Optional[str],
    token: Optional[str],
    base_url: Optional[str] = None,
) -> SourceClient:
    """Create the read client for the configured provider."""
    p = normalize_provider(provider)
    if p == GITLAB:
        return GitLabClient(token=token, base_url=base_url)
    if p == GITHUB:
        return GitHubClient(token=token)
    raise ValueError(
        f"Unsupported REPO_PROVIDER: {provider!r} (expected 'github' or 'gitlab')"
    )


def file_url_pattern(provider: Optional[str], base_url: Optional[str] = None) -> str:
    """Blob-URL template the LLM is told to use when linking code."""
    p = normalize_provider(provider)
    if p == GITLAB:
        return gitlab_file_url_pattern(base_url or GitLabClient.DEFAULT_BASE_URL)
    return GITHUB_FILE_URL_PATTERN
