"""GitLab API client (interface-compatible with shared.github.client)."""

from shared.gitlab.client import GitLabClient, GitLabAPIError

__all__ = ["GitLabClient", "GitLabAPIError"]
