"""Repos API Lambda handlers.

Implements:
- GET /repos/{repoId}/tree - List folder contents
- GET /repos/{repoId}/page - Get page content

Requirements: 7.1, 7.2, 7.3, 7.5
"""

import json
import os
from typing import Any, Optional

from shared.models import TreeNode
from shared.storage.dynamodb import DynamoDBClient
from shared.storage.s3 import S3Client


class APIError(Exception):
    """API error with HTTP status code."""
    
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _get_dynamodb_client() -> DynamoDBClient:
    """Get DynamoDB client with optional LocalStack endpoint."""
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    return DynamoDBClient(endpoint_url=endpoint_url)


def _get_s3_client() -> S3Client:
    """Get S3 client with optional LocalStack endpoint."""
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    return S3Client(endpoint_url=endpoint_url)


def _build_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Build API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def _build_error_response(error: APIError) -> dict[str, Any]:
    """Build error response."""
    return _build_response(
        error.status_code,
        {"error": {"code": error.code, "message": error.message}},
    )


def _get_query_param(event: dict[str, Any], param: str, default: str = "") -> str:
    """Extract query parameter from event."""
    query_params = event.get("queryStringParameters") or {}
    return query_params.get(param, default)


def _get_path_param(event: dict[str, Any], param: str) -> Optional[str]:
    """Extract path parameter from event."""
    path_params = event.get("pathParameters") or {}
    return path_params.get(param)


def _get_repo_id(event: dict[str, Any]) -> str:
    """Extract the repository id (owner/name) from path parameters.

    Supports two shapes:
    - ``repoId``: the full path, possibly containing slashes for GitLab nested
      groups (group/subgroup/project); may be URL-encoded.
    - ``owner`` + ``name``: the classic two-segment form.

    Raises:
        APIError: If the repo id is missing/invalid
    """
    from urllib.parse import unquote

    repo_id = _get_path_param(event, "repoId")
    if repo_id:
        repo_id = unquote(repo_id).strip("/")
        if "/" not in repo_id:
            raise APIError("INVALID_INPUT", "Invalid 'repoId' (expected owner/name)", 400)
        return repo_id

    owner = _get_path_param(event, "owner")
    name = _get_path_param(event, "name")

    if not owner or not name:
        raise APIError("INVALID_INPUT", "Missing 'owner' or 'name' in path", 400)

    return f"{owner}/{name}"


def get_tree(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Get tree nodes (folder contents) for a repository.
    
    GET /repos/{repoId}/tree?branch=...&path=...
    
    Path Parameters:
        repoId: Repository identifier (owner/name)
        
    Query Parameters:
        branch: Branch name (required)
        path: Parent path to query children for (optional, defaults to root "")
    
    Response:
        200: {"nodes": [TreeNode, ...]}
        400: {"error": {"code": "INVALID_INPUT", "message": "..."}}
        404: {"error": {"code": "REPO_NOT_FOUND", "message": "..."}}
        500: {"error": {"code": "INTERNAL_ERROR", "message": "..."}}
    
    Requirements: 7.1, 7.2
    """
    try:
        # Extract parameters
        # Extract parameters
        repo_id = _get_repo_id(event)
        
        branch = _get_query_param(event, "branch")
        if not branch:
            raise APIError("INVALID_INPUT", "Missing 'branch' query parameter", 400)
        
        path = _get_query_param(event, "path", "")
        
        # Get DynamoDB client
        ddb_client = _get_dynamodb_client()
        
        # Query tree nodes (Requirements: 7.1)
        nodes = ddb_client.query_tree(repo_id, branch, path)
        
        # Convert to JSON response format (Requirements: 7.2)
        # Include: type, name, path, and summary availability indicator
        nodes_json = [node.to_json() for node in nodes]
        
        return _build_response(200, {"nodes": nodes_json})
        
    except APIError as e:
        return _build_error_response(e)
    except Exception as e:
        print(f"Internal error: {e}")
        return _build_error_response(
            APIError("INTERNAL_ERROR", "An unexpected error occurred", 500)
        )



def get_page(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Get page content for a repository node.
    
    GET /repos/{repoId}/page?branch=...&path=...
    
    Path Parameters:
        repoId: Repository identifier (owner/name)
        
    Query Parameters:
        branch: Branch name (required)
        path: Node path to get content for (required)
    
    Response:
        200: {
            "usage": "Brief description",
            "summary": "Detailed markdown summary",
            "dependency_graph": "Mermaid diagram or empty",
            "available": true,
            "legacy": false  # Indicates if this is legacy markdown format
        }
        200: {"usage": "", "summary": "", "dependency_graph": "", "available": false}
        400: {"error": {"code": "INVALID_INPUT", "message": "..."}}
        404: {"error": {"code": "NODE_NOT_FOUND", "message": "..."}}
        500: {"error": {"code": "INTERNAL_ERROR", "message": "..."}}
    
    Requirements: 7.3, 7.4, 7.5
    """
    try:
        import json as json_lib
        
        # Extract parameters
        repo_id = _get_repo_id(event)
        
        branch = _get_query_param(event, "branch")
        if not branch:
            raise APIError("INVALID_INPUT", "Missing 'branch' query parameter", 400)
        
        path = _get_query_param(event, "path")
        if path is None:
            raise APIError("INVALID_INPUT", "Missing 'path' query parameter", 400)
        
        # Get clients
        ddb_client = _get_dynamodb_client()
        s3_client = _get_s3_client()
        
        # Get the node from DynamoDB
        node = ddb_client.get_node(repo_id, branch, path)
        
        if not node:
            raise APIError(
                "NODE_NOT_FOUND",
                f"Node '{path}' not found in repository '{repo_id}' branch '{branch}'",
                404,
            )
        
        # Check if summary is available (Requirements: 7.5)
        summary_ref = node.summary_ref
        
        if not summary_ref:
            # No summary available
            return _build_response(200, {
                "usage": "",
                "summary": "",
                "dependency_graph": "",
                "available": False,
                "legacy": False,
            })
        
        # Get the raw content
        if summary_ref.startswith("repos/"):
            # Fetch from S3
            content = s3_client.get_page(summary_ref)
            if content is None:
                return _build_response(200, {
                    "usage": "",
                    "summary": "",
                    "dependency_graph": "",
                    "available": False,
                    "legacy": False,
                })
        else:
            # Inline content in DynamoDB
            content = summary_ref
        
        # Try to parse as JSON (new format)
        try:
            parsed = json_lib.loads(content)
            if isinstance(parsed, dict) and "usage" in parsed and "summary" in parsed:
                return _build_response(200, {
                    "usage": parsed.get("usage", ""),
                    "summary": parsed.get("summary", ""),
                    "dependency_graph": parsed.get("dependency_graph", ""),
                    "available": True,
                    "legacy": False,
                })
        except (json_lib.JSONDecodeError, TypeError):
            pass
        
        # Legacy markdown format - return as-is in summary field
        return _build_response(200, {
            "usage": "",
            "summary": content,
            "dependency_graph": "",
            "available": True,
            "legacy": True,
        })

    except APIError as e:
        return _build_error_response(e)
    except Exception as e:
        print(f"Internal error: {e}")
        return _build_error_response(
            APIError("INTERNAL_ERROR", "An unexpected error occurred", 500)
        )


def list_repos(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List all generated repositories.

    GET /repos

    Response:
        200: {"repos": [{repoId, owner, name, defaultBranch, language, stars, ...}]}
    """
    try:
        ddb_client = _get_dynamodb_client()
        repos = ddb_client.list_repos()
        return _build_response(200, {"repos": [r.to_json() for r in repos]})
    except APIError as e:
        return _build_error_response(e)
    except Exception as e:
        print(f"Internal error: {e}")
        return _build_error_response(
            APIError("INTERNAL_ERROR", "An unexpected error occurred", 500)
        )


def list_source_projects(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """List projects from the configured Git provider (for the catalog table).

    GET /sources/projects?search=&page=

    Currently supports GitLab (REPO_PROVIDER=gitlab). For other providers it
    returns an empty list so the UI can fall back to the search box.

    Response:
        200: {"projects": [{pathWithNamespace, name, defaultBranch, starCount, ...}],
              "nextPage": int|null, "provider": "gitlab"}
    """
    try:
        provider = os.environ.get("REPO_PROVIDER", "github").strip().lower()
        if provider != "gitlab":
            return _build_response(200, {"projects": [], "nextPage": None, "provider": provider})

        search = _get_query_param(event, "search", "")
        try:
            page = int(_get_query_param(event, "page", "1") or "1")
        except ValueError:
            page = 1

        token = os.environ.get("GITLAB_TOKEN")
        base_url = os.environ.get("GITLAB_URL")

        import asyncio
        import aiohttp
        from shared.gitlab.client import GitLabClient, GitLabAPIError

        # When searching, scan pages and fuzzy-match locally so the query also
        # matches the project description (GitLab's own search only covers name/path).
        MAX_SEARCH_SCAN = 600

        async def _run():
            client = GitLabClient(token=token, base_url=base_url)
            try:
                if not search:
                    return await client.list_projects(search="", page=page)

                scanned: list[dict] = []
                p = 1
                while p and len(scanned) < MAX_SEARCH_SCAN:
                    batch, nxt = await client.list_projects(search="", page=p, per_page=100)
                    scanned.extend(batch)
                    p = nxt

                q = search.lower()
                matched = [
                    pr for pr in scanned
                    if q in (pr.get("pathWithNamespace") or "").lower()
                    or q in (pr.get("name") or "").lower()
                    or q in (pr.get("description") or "").lower()
                ]
                return matched, None
            finally:
                await client.close()

        host = base_url or "https://gitlab.com"
        try:
            projects, next_page = asyncio.run(_run())
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            print(f"Source provider unreachable: {e}")
            raise APIError(
                "SOURCE_UNREACHABLE",
                f"无法连接到 Git 服务({host}),请检查网络 / VPN 后重试",
                502,
            )
        except GitLabAPIError as e:
            print(f"Source provider error: {e}")
            raise APIError(
                "SOURCE_ERROR",
                f"Git 服务返回错误({e.status_code}),请检查 GITLAB_TOKEN / GITLAB_URL",
                502,
            )

        return _build_response(200, {
            "projects": projects,
            "nextPage": next_page,
            "provider": provider,
        })
    except APIError as e:
        return _build_error_response(e)
    except Exception as e:
        print(f"Internal error: {e}")
        return _build_error_response(
            APIError("INTERNAL_ERROR", "An unexpected error occurred", 500)
        )
