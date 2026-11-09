import json
from typing import List, Dict, Any, Generator
from openai import OpenAI
from src.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

_llm_client: OpenAI | None = None

def get_llm_client() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        if not LLM_API_KEY:
            raise ValueError("LLM_API_KEY is not set or empty in .env")
        _llm_client = OpenAI(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY.strip()
        )
    return _llm_client

def stream_rag_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] | None = None
) -> Generator[str, None, None]:
    """
    Generator that yields SSE-formatted data chunks:
    1. First event: 'sources' metadata JSON.
    2. Subsequent events: individual text tokens.
    3. Final event: '[DONE]'.
    """
    client = get_llm_client()

    # 1. Format context chunks
    formatted_context = ""
    for idx, c in enumerate(context_chunks, 1):
        doc_type = c.get("doc_type", "Document")
        page = c.get("page_number", "N/A")
        content = c.get("content", "")
        formatted_context += f"--- Source {idx} [{doc_type} | Page {page}] ---\n{content}\n\n"

    system_prompt = (
        "You are an academic AI teaching assistant. Answer the student's question accurately, "
        "concisely, and thoroughly based strictly on the provided course material sources.\n"
        "Cite the sources or page numbers whenever applicable. If the provided context does not contain "
        "sufficient information to answer the question, state that clearly rather than hallucinating."
    )

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_prompt = (
        f"Context from course materials:\n\n{formatted_context}\n"
        f"Student Question: {query}"
    )
    messages.append({"role": "user", "content": user_prompt})

    # First: emit the retrieved grounding sources so the frontend can render citation pills immediately
    sources_payload = json.dumps({"type": "sources", "data": context_chunks})
    yield f"data: {sources_payload}\n\n"

    # Call LLM with stream=True
    try:
        response_stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
            stream=True  # <-- Enables streaming generator from API
        )

        for chunk in response_stream:
            # Check if this delta contains a token
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                token = delta.content or ""
                if token:
                    token_payload = json.dumps({"type": "token", "data": token})
                    yield f"data: {token_payload}\n\n"

    except Exception as e:
        error_payload = json.dumps({"type": "error", "data": str(e)})
        yield f"data: {error_payload}\n\n"

    # Signal completion
    yield "data: [DONE]\n\n"