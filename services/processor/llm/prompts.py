"""Prompt templates for LLM summarization.

Ported from src/agent/prompt.py for the AWS serverless architecture.

Requirements: 5.6, 5.7
"""


# Blob-URL templates the LLM is instructed to use when linking code.
# The model fills in {owner}/{repo}/{commitSha}/{path}/{lineStart}/{lineEnd}.
GITHUB_FILE_URL_PATTERN: str = (
    "https://github.com/{owner}/{repo}/blob/{commitSha}/{path}#L{lineStart}-L{lineEnd}"
)


def gitlab_file_url_pattern(base_url: str = "https://gitlab.com") -> str:
    """GitLab blob-URL template (note the '/-/blob/' segment and '#L1-2' anchor)."""
    return (
        base_url.rstrip("/")
        + "/{owner}/{repo}/-/blob/{commitSha}/{path}#L{lineStart}-{lineEnd}"
    )


# Placeholder inside the prompt bodies, swapped for the provider pattern by
# code_prompt() / folder_prompt() below.
_FILE_URL_SENTINEL: str = "<<FILE_URL_PATTERN>>"


CODE_PROMPT: str = """
You are an expert software engineer and your task is to deeply analyze a provided codebase from a code repository. Your goal is to generate a comprehensive and structured summary of the codebase that is suitable for a developer-friendly wiki page in markdown format but without backticks.

**Input:**

You will receive the following information, extracted from a GitHub repository:

1. **Repository Description:**
*   'description': (A textual description of the repository, although it may not be available or be correct)
2. **Code File:**
* The raw content of code files within the repository.
* The owner of the repository.
* The repository name.
* The commit sha of the repository.
* The path to the code file within the repository.

**Analysis Tasks:**

1. **High-Level Overview:**
*   Provide a concise summary of the file responsibilities and functionalities based on it's content.
*   Explain its role in the overall system.
*   Identify its dependencies on other modules/components.
*   Highlight any important classes, functions, or data structures.
*   Link all the code blocks (Class,Function,Enum,Exception) that are referenced using the following markdown link format: [`Description of Code Block`](Full url of the file including the start line with optional ending line#L{startLine}-L{endLine}). This is in the form of "<<FILE_URL_PATTERN>>".
2. **Code-Level Insights:**
*   Analyze the code files to understand the implementation details.
*   Identify core algorithms, data structures, and design patterns used.
*   Provide a summary of how data flows between different parts of the system.
3. **Dependencies and Relationships:**
*   Clearly document the relationships between different modules, classes, and functions.
*   Explain how different parts of the codebase interact with each other.

**Output:**
"""


FOLDER_PROMPT: str = """
You are an expert software engineer and your task is to deeply analyze a provided codebase from a code repository. Your goal is to generate a comprehensive and structured summary of the codebase that is suitable for a developer-friendly wiki page in markdown format but without backticks.

**Input:**

You will receive the following information, summarized from the expert software engineer:

1. **Repository Description:**
*   'description': (A textual description of the repository, although it may not be available or be correct)
2. **Code Files:**
* The summary of code files within the repository.
* The owner of the repository.
* The repository name.
* The commit sha of the repository.
* The path to the code file within the repository.
3. **Import/Dependency Information (if provided):**
* Raw import statements detected in each file to help understand dependencies.

**Analysis Tasks:**

1. **High-Level Overview:**
*   Start by providing the core functionality among the folders or files. (ex. the folder name "core", "src" or folder with the same repository name usually contains the core functionality of the system. You can ignore utility folders unless they contain important information or there are nothing to explain.)
*   Provide a concise summary of the folder's responsibilities and functionalities based on it's sub-files and sub-folders summaries.
*   Explain its role in the overall system.
*   Identify its dependencies on other modules/components/folder.
*   Highlight any important classes, functions, or data structures in it's sub-files and sub-folders.
*   Link all the code blocks that are referenced using the following markdown link format: [`Description of Code Block`](Full url of the file including the start line with optional ending line#L{startLine}-L{endLine}). This is in the form of "<<FILE_URL_PATTERN>>".

2. **Dependencies and Relationships:**
*   Clearly document the relationships between different folders and files.
*   Explain how different parts of the codebase interact with each other.

3. **Dependency Graph (Mermaid):**
*   Generate a Mermaid flowchart (graph TD) showing file relationships WITHIN this folder.
*   Use SHORT labeled arrows (under 5 words) that describe the relationship/action.
*   Good labels: "provides config to", "transforms data for", "reports errors to", "validates input for", "extends", "implements", "fetches from", "stores in", "parses for", "informs", "uses models from"
*   Only show meaningful relationships between files in this folder.
*   CRITICAL: Use SAFE, alphanumeric identifiers for nodes (no special chars like /, @, -, or spaces). Use the filename as the LABEL.
*   Format: safe_id["Filename"]
*   Example:
    graph TD
        services["services"] -->|uses models from| shared_models["@shared/models"]
        api_client["api-client"] -->|calls| backend_api["backend/api"]
        views -->|delegates to| services
        tasks -->|async wrapper for| services
        config -->|provides settings to| services

**Output:**
"""


FILE_PROMPT_TEMPLATE: str = """The following instruction is given:
{requirements}
{format_instructions}
The given repository owner is {repo_owner} with repository name of {repo_name}
The commit SHA referenced is {commit_sha}
The path of the file is {path}
Below is the code for your task: {code}"""


FOLDER_PROMPT_TEMPLATE: str = """The following instruction is given:
{requirements}
{format_instructions}
The given repository owner is {repo_owner} with repository name of {repo_name}
The commit SHA referenced is {commit_sha}
The path of the folder is {path}
Below are the summaries for the codebase:
{ai_summaries}"""


# Default output language for generated summaries.
DEFAULT_LANGUAGE: str = "zh"

_ZH_ALIASES = {"zh", "zh-cn", "zh_cn", "chinese", "cn", "中文"}


def _language_directive(language: str, *, graph_note: bool) -> str:
    """Instruction forcing the prose output into the target language.

    Returns an empty string for English (the prompts are already English).
    The dependency graph is always kept English/structural.
    """
    lang = (language or DEFAULT_LANGUAGE).strip().lower()
    if lang not in _ZH_ALIASES:
        return ""
    directive = (
        "\n\n**Output language:** Write the `usage` and `summary` text in "
        "Simplified Chinese (简体中文). Keep all code identifiers, class / function / "
        "variable names, file paths, and URLs exactly as-is — do NOT translate or "
        "alter them."
    )
    if graph_note:
        directive += (
            " For the Mermaid dependency graph, keep BOTH the node identifiers and the "
            "edge labels in English / structural form (e.g. \"uses\", \"provides config "
            "to\") — do not translate the graph."
        )
    return directive


def code_prompt(
    file_url_pattern: str = GITHUB_FILE_URL_PATTERN,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """CODE_PROMPT with the blob-URL pattern and output-language directive applied."""
    return (
        CODE_PROMPT.replace(_FILE_URL_SENTINEL, file_url_pattern)
        + _language_directive(language, graph_note=False)
    )


def folder_prompt(
    file_url_pattern: str = GITHUB_FILE_URL_PATTERN,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """FOLDER_PROMPT with the blob-URL pattern and output-language directive applied."""
    return (
        FOLDER_PROMPT.replace(_FILE_URL_SENTINEL, file_url_pattern)
        + _language_directive(language, graph_note=True)
    )
