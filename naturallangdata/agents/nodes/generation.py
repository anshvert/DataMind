"""Generation node — pass reranked context to the LLM and produce an answer."""
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from naturallangdata.agents.state import QueryState
from naturallangdata.core.config import Settings

_SYSTEM = (
    "You are a precise, factual question-answering assistant. "
    "Answer using ONLY the context provided below. "
    "If the answer is not present, say so explicitly. "
    "When quoting information, prefix it with the source document name in brackets."
)

_HUMAN = "Question: {question}\n\nContext:\n{context}"


def make_generation_node(settings: Settings):
    llm = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers={
            "HTTP-Referer": settings.openrouter_site_url,
            "X-Title": settings.openrouter_app_name,
        },
    )
    chain = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)]) | llm

    def generation_node(state: QueryState) -> QueryState:
        try:
            docs = state.get("reranked_docs") or state.get("retrieved_docs", [])
            context = (
                "\n\n".join(f"[{d['doc_name']}] {d['text']}" for d in docs)
                or "No relevant context found."
            )
            result = chain.invoke({"question": state["question"], "context": context})
            answer = result.content if hasattr(result, "content") else str(result)
            sources = [
                {
                    "doc_id": d["doc_id"],
                    "doc_name": d["doc_name"],
                    "text": d["text"],
                    "score": float(d.get("score", 0.0)),
                }
                for d in docs
            ]
            return {**state, "answer": answer, "sources": sources, "status": "done"}
        except Exception as exc:
            return {**state, "status": "error", "error": f"generation failed: {exc}"}

    return generation_node
