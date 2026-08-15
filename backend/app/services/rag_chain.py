import logging
import operator
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from pydantic import SecretStr
from .retrieval import retrieval_service
from .embeddings import embedding_service
from ..vectorstore.qdrant import qdrant_service
from ..prompts.chat_prompt import chat_prompt
from ..config.settings import settings

logger = logging.getLogger(__name__)


model_display = {
    "gpt-oss-120b": "Groq (GPT-OSS 120B)",
    "gpt-oss-20b":  "Groq (GPT-OSS 20B)",
}

Expanded_query_prompt = ChatPromptTemplate.from_template(
    "You are an AI assistant helping to improve search results. "
    "Generate exactly 2 alternate search queries that are similar in meaning to the original query. "
    "These queries should use different keywords or phrasing to find relevant documents. "
    "Return ONLY the alternate queries, one per line, without numbers, bullet points, or any other text.\n\n"
    "Original query: {query}"
)

def detect_format_instruction(query: str) -> str:
    q = query.lower()
    if "summary" in q or "summarize" in q:
        return "Use the SUMMARY Response Format."
    elif "revision notes" in q or "notes" in q:
        return "Use the REVISION NOTES Response Format."
    elif "flashcard" in q:
        return "Use the FLASHCARDS Response Format."
    elif "quiz" in q or "mcq" in q:
        return "Use the QUIZ Response Format."
    elif "compare" in q or "difference" in q:
        return "Use the COMPARISON Response Format."
    elif "define" in q or "definition" in q:
        return "Use the DEFINITIONS Response Format."
    elif "algorithm" in q or "procedure" in q or "steps" in q:
        return "Use the ALGORITHMS / PROCEDURES Response Format."
    elif "code" in q or "program" in q:
        return "Use the PROGRAMMING QUESTIONS Response Format."
    return "Use the GENERAL RESPONSE FORMAT."


class RAGState(TypedDict, total=False):
    query: str
    file_id: Optional[int]
    expanded_queries: List[str]
    documents: List[Any]
    context: str
    format_instruction: str

    providers_to_try: List[str]
    provider_used: Optional[str]
    errors: Annotated[List[str], operator.add]

    answer: str
    sources: List[str]
    timestamps: List[dict]


class RAGChainService:
    _instance: Optional["RAGChainService"] = None
    _graph: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # Create the Models
    def create_model(self, model_name: str) -> ChatGroq:
        return ChatGroq(
            model=model_name,
            api_key=SecretStr(settings.GROQ_API_KEY),
            temperature=0.2,
            max_retries=0,
            max_tokens=2500
        )

    def build_llm_for_provider(self, provider: str) -> Any:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set.")
        if provider == "gpt-oss-120b":
            return self.create_model("openai/gpt-oss-120b")
        elif provider == "gpt-oss-20b":
            return self.create_model("openai/gpt-oss-20b")
        raise ValueError(f"Unknown provider: {provider}")

    def get_fallback_providers(self) -> List[str]:
        return ["gpt-oss-20b"] if settings.LLM_PROVIDER == "gpt-oss-120b" else []

    #Expand the Query for vaguelessness
    def expand_query_node(self, state: RAGState) -> Dict[str, Any]:
        query = state["query"]
        alternates: List[str] = []
        try:
            llm = self.build_llm_for_provider(settings.LLM_PROVIDER)
            expand_chain = Expanded_query_prompt | llm | StrOutputParser()
            content = expand_chain.invoke({"query": query})
            alts = [q.strip().lstrip("- *") for q in content.split("\n") if q.strip()]
            alternates = [q for q in alts if q][:2]
        except Exception as e:
            logger.warning("Query expansion failed: %s", e)

        expanded_queries = [query] + alternates
        logger.info("Expanded queries for retrieval: %s", expanded_queries)
        return {"expanded_queries": expanded_queries}

    # Retrieve Node Of Graph
    def retrieve_node(self, state: RAGState) -> Dict[str, Any]:
        queries = state.get("expanded_queries") or [state["query"]]
        file_id: Optional[int] = state.get("file_id")
        number_of_results = 10

        results_per_query = []
        for q in queries:
            docs = retrieval_service.retrieve_documents(
                q,
                number_of_results=number_of_results,
                filter_by_file_id=file_id,
            )
            results_per_query.append(docs)

        merged_docs: List[Any] = []
        seen_contents: set = set()
        max_docs = max((len(docs) for docs in results_per_query), default=0)
        for i in range(max_docs):
            for docs in results_per_query:
                if i < len(docs):
                    doc = docs[i]
                    if doc.page_content not in seen_contents:
                        seen_contents.add(doc.page_content)
                        merged_docs.append(doc)

        documents = merged_docs[:number_of_results]
        documents.sort(key=lambda d: d.metadata.get("chunk_number", 0))

        formatted = []
        for document in documents:
            source = document.metadata.get("filename", "Unknown")
            source_type = document.metadata.get("source_type", "document")
            metadata_str = f"Document:\n{source}\n"

            if source_type in ["video", "audio"]:
                ts_start = document.metadata.get("timestamp_start")
                ts_end = document.metadata.get("timestamp_end")
                if ts_start and ts_end:
                    metadata_str += f"\nTimestamp:\n{ts_start}s - {ts_end}s\n"

            formatted.append(f"{metadata_str}\nContent:\n{document.page_content}")

        context = "\n\n-------------------------------------\n\n".join(formatted)

        sources = list(set(doc.metadata.get("filename", "Unknown") for doc in documents))
        timestamps = [
            {
                "filename": doc.metadata.get("filename"),
                "start": doc.metadata.get("timestamp_start"),
                "end": doc.metadata.get("timestamp_end"),
            }
            for doc in documents
            if doc.metadata.get("timestamp_start") and doc.metadata.get("timestamp_end")
        ]

        format_instruction: str = detect_format_instruction(state["query"])

        return {
            "documents": documents,
            "context": context,
            "sources": sources,
            "timestamps": timestamps,
            "format_instruction": format_instruction,
        }

    # Generate Node Of Graph
    def generate_node(self, state: RAGState) -> Dict[str, Any]:
        providers_to_try: List[str] = state.get("providers_to_try") or []

        if not providers_to_try:
            return {
                "provider_used": None,
                "answer": (
                    "I'm sorry, I wasn't able to generate a response right now. "
                    "All available AI providers are temporarily unavailable. "
                    "Please check your API key and try again in a moment."
                ),
            }

        provider = providers_to_try[0]
        display_name = model_display.get(provider, provider)

        try:
            logger.info("Sending request to %s...", display_name)
            llm = self.build_llm_for_provider(provider)
            generation_chain = chat_prompt | llm | StrOutputParser()
            content = generation_chain.invoke({
                "context": state.get("context", ""),
                "question": state["query"],
                "format_instruction": state.get("format_instruction", "Use the GENERAL RESPONSE FORMAT."),
            })

            if not content or not content.strip():
                raise ValueError("Model returned an empty response.")

            if provider != settings.LLM_PROVIDER:
                logger.info(
                    "Primary provider (%s) failed. Answer generated by fallback: %s.",
                    model_display.get(settings.LLM_PROVIDER, settings.LLM_PROVIDER),
                    display_name,
                )

            return {
                "answer": content,
                "provider_used": provider,
                "providers_to_try": providers_to_try[1:],
            }

        except Exception as e:
            logger.warning(
                "%s could not answer this time (%s). Trying next option...", display_name, e
            )
            return {
                "errors": [str(e)],
                "providers_to_try": providers_to_try[1:],
                "provider_used": None,
            }

    # Check The Success of Model Availability
    def check_generation_success(self, state: RAGState) -> str:
        if state.get("provider_used"):
            return "success"
        remaining = state.get("providers_to_try") or []
        return "retry" if remaining else "failed"

    # Building the Whole Graph
    def _build_graph(self):
        """Compiles the LangGraph StateGraph for the RAG pipeline."""
        workflow: StateGraph = StateGraph(RAGState)

        workflow.add_node("expand_query", self.expand_query_node)
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("generate", self.generate_node)

        workflow.set_entry_point("expand_query")
        workflow.add_edge("expand_query", "retrieve")
        workflow.add_edge("retrieve", "generate")

        workflow.add_conditional_edges(
            "generate",
            self.check_generation_success,
            {
                "success": END,
                "retry": "generate",
                "failed": END,
            },
        )

        self._graph = workflow.compile()

    # Intialization of Graph
    def initialize(self):
        if not qdrant_service.vectorstore:
            qdrant_service.initialize(embedding_service.get_embeddings())
        if self._graph is None:
            self._build_graph()

    # Invoke the Graph
    def invoke(self, query: str, file_id: Optional[int] = None) -> Dict[str, Any]:
        if self._graph is None:
            self.initialize()
        assert self._graph is not None, "Graph failed to initialize"

        primary = settings.LLM_PROVIDER
        providers = [primary] + self.get_fallback_providers()

        initial_state: RAGState = {
            "query": query,
            "file_id": file_id,
            "providers_to_try": providers,
            "errors": [],
        }

        final_state: Dict[str, Any] = self._graph.invoke(initial_state)

        if not final_state.get("provider_used"):
            return {
                "answer": final_state.get("answer", "I'm sorry, I couldn't generate a response. Please try again."),
                "sources": [],
                "timestamps": [],
                "context_used": "",
                "provider_used": None,
            }

        provider_used: str = final_state["provider_used"]
        answer: str = final_state.get("answer", "")

        provider_note = ""
        if provider_used != settings.LLM_PROVIDER:
            provider_note = (
                "\n\n---\n"
                "_🔄 Just so you know — our primary AI assistant had a small hiccup, "
                "so a backup assistant stepped in and answered this for you. "
                "The answer is just as accurate — you might not even notice the difference!_"
            )

        return {
            "answer": answer + provider_note,
            "sources": final_state.get("sources", []),
            "timestamps": final_state.get("timestamps", []),
            "context_used": (final_state.get("context") or "")[:500],
            "provider_used": provider_used,
        }


rag_chain_service = RAGChainService()
