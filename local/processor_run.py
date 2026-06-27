"""Local dev runner for the repository processor against LocalStack.

Step Functions is not emulated locally, so the SendTaskSuccess / SendTaskFailure
callbacks are stubbed out. Everything else (GitHub fetch, tree filtering, LLM
summarization, DynamoDB / S3 writes) runs exactly as it does in production.

Invoked by local/process-repo.sh via the `processor` compose service.
Repo coordinates are supplied through environment variables:
    REPO_OWNER, REPO_NAME, JOB_ID  (BRANCH optional)
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from services.processor.main import RepositoryProcessor, ProcessorConfig  # noqa: E402


async def _run() -> int:
    config = ProcessorConfig.from_environment()
    processor = RepositoryProcessor(config)
    # No Step Functions locally — neutralize the completion callbacks.
    processor._send_task_success = lambda: None
    processor._send_task_failure = lambda stage, error: None
    await processor.run()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
