# DataMind

A learning-first document RAG app built with FastAPI and the LangChain ecosystem.

## Setup

1. Create a `.env` file with your OpenRouter API key:

```bash
OPENROUTER_API_KEY=your_key_here
```

2. Install dependencies:

```bash
pip install fastapi uvicorn python-multipart pypdf pymupdf python-docx langchain langchain-openai langchain-text-splitters sentence-transformers faiss-cpu numpy python-dotenv
```

3. Start the server:

```bash
uvicorn app:app --reload
```

## Endpoints

- `GET /health`
- `POST /documents/upload` (supports PDF and DOCX)
- `POST /query/`
- `GET /documents/`
