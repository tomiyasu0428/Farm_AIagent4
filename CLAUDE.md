# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an agricultural AI management system built with FastAPI, LangChain/LangGraph, and MongoDB. The system provides a LINE Bot interface for farmers to manage work logs, field information, and receive AI-powered farming advice through natural language processing.

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables (copy from .env.example if available)
# Required variables:
# - GOOGLE_API_KEY (Google AI API)
# - MONGODB_CONNECTION_STRING (MongoDB connection)
# - LINE_CHANNEL_ACCESS_TOKEN (LINE Bot)
# - LINE_CHANNEL_SECRET (LINE Bot)
# - LANGSMITH_API_KEY (optional, for tracing)
```

### Running the Application
```bash
# Run the main FastAPI application (LINE Bot webhook)
python src/agri_ai/line_bot/webhook.py

# Or using uvicorn
uvicorn src.agri_ai.line_bot.webhook:app --host 0.0.0.0 --port 8000

# Run example/demo scripts
python docs/examples/confirmation_flow_example.py
```

### Available Endpoints
- `GET /` - Root endpoint (health check)
- `GET /health` - Detailed health check with MongoDB status
- `POST /webhook` - LINE Bot webhook endpoint
- `POST /push` - Push message endpoint (development/testing)

## Architecture Overview

### Multi-Agent System Design
The system uses a **hierarchical multi-agent architecture** with:

- **MasterAgent** (`src/agri_ai/core/master_agent.py`): Central orchestrator that analyzes queries and routes to specialized agents
- **Specialized Agents**: Domain-specific agents for different agricultural tasks:
  - `WorkLogRegistrationAgent`: Natural language work report processing
  - `WorkLogSearchAgent`: Historical work record querying  
  - `FieldAgent`: Farm field information management
  - `FieldRegistrationAgent`: New field registration workflows

### Agent Communication
Agents communicate through **LangChain custom tools** rather than direct calls:
- `WorkLogRegistrationAgentTool`: Work logging with confirmation flows
- `FieldAgentTool`: Field information queries
- `WorkLogSearchAgentTool`: Historical data searches

### LangGraph Migration
A **LangGraph prototype** exists in `langgraph_prototype/` implementing:
- State-based workflow with `AgriAgentState`
- Supervisor pattern for agent coordination
- Graph-based routing between specialized agents

### Database Design
Uses **MongoDB** with domain-driven document structure:
- `work_logs`: Time-series work records with embedded extracted data
- `fields`: Field master data with geospatial and cultivation info
- `crops`: Crop master with cultivation calendars
- `materials`: Agricultural materials with usage restrictions
- `workers`: User management with LINE integration

All database interactions use **Pydantic models** for type safety.

### LINE Bot Integration
FastAPI webhook (`src/agri_ai/line_bot/webhook.py`) with:
- Async message processing with timeout handling
- **Confirmation middleware** for user interaction flows
- Session management for conversation context
- Redis-backed conversation memory

### Key Architectural Patterns

**Strategy Pattern**: Registration workflows (`src/agri_ai/strategies/`) provide flexible processing:
- `AutoRegistrationStrategy`: High-confidence direct registration
- `IntelligentStrategy`: LLM-based decision making
- `ConfirmationStrategy`: User confirmation workflows

**Dependency Injection**: Comprehensive DI through `IServiceProvider` interface for service abstraction and testability.

**Layered Architecture**:
- **Core Layer** (`src/agri_ai/core/`): Configuration, base abstractions, session management
- **Service Layer** (`src/agri_ai/services/`): Business logic (extraction, validation, query analysis)
- **Gateway Layer** (`src/agri_ai/gateways/`): External service integrations
- **Domain Layer** (`src/agri_ai/domain/`): Business logic for data matching and scoring

## Important Implementation Notes

### Confirmation Flows
Many operations require user confirmation, implemented through middleware patterns. The system uses **HTML comment-based data embedding** for state persistence across LINE messages.

### Error Handling
The system implements comprehensive error handling with:
- Multiple fallback mechanisms for service failures
- Graceful degradation when external services fail
- Timeout handling for async operations

### Memory Management
- **Redis-backed conversation memory** for production
- **In-memory fallback** when Redis is unavailable
- Session management with user/thread isolation

### Configuration
All configuration is managed through `src/agri_ai/core/config.py` using Pydantic settings with environment variable support.

## Testing

**Note**: This project currently lacks formal testing infrastructure (no pytest.ini, test files, or CI/CD). When adding tests, consider:
- Testing strategy-based workflows
- Mocking external services (MongoDB, Redis, Google AI API, LINE Bot API)
- Testing confirmation flow state transitions
- Testing multi-agent communication patterns

## Development Workflow

1. Make sure all required environment variables are set
2. Run the FastAPI application for LINE Bot testing
3. Use example scripts to test individual components
4. Monitor logs for LangSmith tracing (if enabled)
5. Check `/health` endpoint for system status

The system is production-ready with robust error handling, but is actively evolving toward LangGraph-based agent orchestration.