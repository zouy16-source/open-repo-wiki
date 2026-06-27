"""Minimal local HTTP server fronting the API Lambda handlers.

Translates incoming HTTP requests into API Gateway proxy events and
dispatches them to services.api.lambda_handler. For local development
against LocalStack only. The production HMAC authorizer is bypassed here.

Routes:
    POST   /jobs
    GET    /jobs/{jobId}
    GET    /repos/{owner}/{name}/tree?branch=...&path=...
    GET    /repos/{owner}/{name}/page?branch=...&path=...
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, "/app")

from services.api.lambda_handler import jobs_handler, repos_handler  # noqa: E402


def _single(qs: dict) -> dict:
    """Collapse parse_qs lists into single values."""
    return {key: values[0] for key, values in qs.items()}


def _invoke(handler, event):
    """Call a Lambda handler and normalize its API Gateway response."""
    response = handler(event, None)
    status = response.get("statusCode", 200)
    raw_body = response.get("body", "")
    try:
        payload = json.loads(raw_body) if raw_body else ""
    except (json.JSONDecodeError, TypeError):
        payload = raw_body
    return status, payload


def _dispatch(method: str, path: str, query: str, body: str):
    if method == "OPTIONS":
        return 200, ""

    segments = [seg for seg in path.split("/") if seg != ""]
    if not segments:
        return 404, {"error": {"code": "NOT_FOUND", "message": path}}

    query_params = _single(parse_qs(query, keep_blank_values=True))
    root = segments[0]

    if root == "jobs":
        if method == "POST" and len(segments) == 1:
            return _invoke(jobs_handler, {
                "httpMethod": "POST",
                "resource": "/jobs",
                "body": body,
            })
        if method == "GET" and len(segments) == 2:
            return _invoke(jobs_handler, {
                "httpMethod": "GET",
                "resource": "/jobs/{jobId}",
                "pathParameters": {"jobId": segments[1]},
            })

    if root == "repos" and len(segments) >= 4 and method == "GET":
        action = segments[-1]                  # 'tree' or 'page'
        repo_id = "/".join(segments[1:-1])     # supports nested GitLab groups
        if action in ("tree", "page"):
            return _invoke(repos_handler, {
                "httpMethod": "GET",
                "resource": f"/repos/{{repoId}}/{action}",
                "pathParameters": {"repoId": repo_id},
                "queryStringParameters": query_params or None,
            })

    return 404, {"error": {"code": "NOT_FOUND", "message": path}}


class Handler(BaseHTTPRequestHandler):
    def _handle(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8") if length else "{}"

        try:
            status, payload = _dispatch(self.command, parsed.path, parsed.query, body)
        except Exception as exc:  # noqa: BLE001
            status, payload = 500, {"error": {"code": "LOCAL_ERROR", "message": str(exc)}}

        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Signature,X-Timestamp")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _handle
    do_POST = _handle
    do_OPTIONS = _handle

    def log_message(self, fmt, *args):
        sys.stderr.write("[api] " + (fmt % args) + "\n")


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[api] local API server listening on http://0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
