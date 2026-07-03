# VEGAH Backend - FastAPI Application

FastAPI backend service for RFP compliance analysis with LangGraph agent orchestration, vector search, and multi-LLM support.

## Project Structure

```
backend/
├── main.py                  # FastAPI app entry point with SSE streaming
├── config.py                # Configuration and settings
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (API keys, Qdrant config)
├── agents/                  # LangGraph agent definitions
│   ├── action_agent.py      # Action extraction agent
│   ├── extraction_agent.py  # RFP extraction agent
│   ├── intake_agent.py      # Initial processing agent
│   ├── rag_agent.py         # Vector search retrieval agent
│   ├── reasoning_agent.py   # Analysis and reasoning agent
│   ├── validator_agent.py   # Compliance validation agent
│   └── graph.py             # Agent graph orchestration
├── models/                  # Pydantic data models
│   ├── schemas.py           # Request/response schemas
│   ├── state.py             # Application state model
│   └── __init__.py
├── services/                # Business logic services
│   ├── csv_parser.py        # CSV parsing and processing
│   ├── pdf_parser.py        # PDF parsing using PDFPlumber
│   ├── embeddings.py        # Vector embeddings generation
│   ├── qdrant_service.py    # Vector database operations
│   └── __init__.py
└── __init__.py
```

## Setup

### Install Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Environment Configuration

Create a `.env` file with:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GROQ_API_KEY=gsk_...
QDRANT_URL=https://...aws.cloud.qdrant.io
QDRANT_API_KEY=eyJ...
DEBUG=true
CAPABILITIES_COLLECTION=vegah_capabilities
PROPOSALS_COLLECTION=vegah_proposals
```

## Running the Server

### Development (with auto-reload)

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Access API docs at: http://localhost:8000/docs

## API Endpoints

### Health Check

```
GET /health
```

Returns server status and Qdrant connection status.

### Upload Capabilities

```
POST /api/upload-capabilities
Content-Type: multipart/form-data

Body: CSV file
```

Parses CSV, generates embeddings, stores in Qdrant.

### Process RFP (Streaming)

```
POST /api/process-rfp
Content-Type: application/json

{
  "pdf_content": "base64_encoded_pdf",
  "model": "claude-3-5-sonnet",
  "temperature": 0.7
}
```

Streams compliance analysis in real-time using Server-Sent Events (SSE).

## Agent Architecture

The system uses a multi-agent reasoning chain via LangGraph:

1. **Intake Agent** - Preprocesses RFP and extracts key information
2. **Extraction Agent** - Identifies requirements from RFP text
3. **RAG Agent** - Retrieves matching capabilities from vector database
4. **Action Agent** - Suggests compliance actions
5. **Reasoning Agent** - Analyzes gaps and generates insights
6. **Validator Agent** - Verifies compliance assertions

See `agents/graph.py` for orchestration logic.

## Vector Database (Qdrant)

- Collection: `vegah_capabilities` - Stores company capabilities
- Collection: `vegah_proposals` - Stores RFP documents
- Embedding Model: OpenAI's text-embedding-3-small or Anthropic's embeddings

## Development

### Format Code

```bash
black *.py agents/ models/ services/
```

### Type Checking

```bash
mypy main.py
```

## Production Deployment

See root [DEPLOYMENT.md](../DEPLOYMENT.md) for Render deployment guide.

For self-hosted deployment:

- Use `gunicorn` or `uvicorn` with multiple workers
- Set `DEBUG=false` in `.env`
- Configure CORS for frontend origin
- Use reverse proxy (nginx) for SSL/TLS
