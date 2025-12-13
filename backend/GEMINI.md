# Product Overview

PaperPlane is an event-driven omnichannel messaging platform designed for student recruitment and medical tourism agencies. The system serves as a central communication hub that integrates AI-powered lead generation with multi-channel messaging capabilities.

## Core Value Proposition

PaperPlane enables agencies to:
- Discover and engage potential clients through AI-powered lead generation
- Manage omnichannel communications (WhatsApp, etc.) via a unified platform
- Automate outreach with AI-generated personalized messages
- Track client journeys from prospect to closed deal

## Key Features

### For Agencies
- **AI Lead Generation Pipeline**: Four-agent system (Scout, Navigator, Researcher, Strategist) that discovers prospects, extracts decision-maker contact information, enriches contact data, and drafts personalized outreach messages
- **Omnichannel Messaging**: Unified interface for WhatsApp and other messaging platforms via Twilio integration
- **Custom Form Builder**: Create shareable forms with QR codes for client data collection
- **Service Monitoring**: Track flight prices, rental prices, and other relevant services
- **AI-Assisted Q&A**: Automated responses to common client questions

### For Clients
- **Consultation Booking**: Schedule appointments with agency representatives
- **Document Management**: Upload and update required documentation
- **Real-time Updates**: Receive notifications about application progress
- **Service Recommendations**: Get AI-curated flight and rental options

## AI Lead Generation Pipeline

The core AI pipeline consists of four specialized agents working in sequence:

### 1. Scout Agent
- **Purpose**: Partner discovery through Google Maps scraping
- **Technology**: Playwright-based browser automation
- **Output**: Raw business data (name, website, address, reviews)
- **Key Features**: Market-specific search queries, anti-detection measures, rate limiting

### 2. Navigator Agent  
- **Purpose**: Systematic contact extraction from partner websites
- **Technology**: Crawl4AI with Playwright for dynamic content rendering
- **V2 Approach**: Simplified systematic extraction without relevance filtering
- **Output**: Comprehensive contact information (decision-maker names, emails, phone numbers, social media)
- **Key Features**: Header/footer navigation prioritization, comprehensive contact extraction, name association, structured schema output

### 3. Researcher Agent
- **Purpose**: Contact data enhancement and fallback enrichment
- **Technology**: Traditional web scraping with BeautifulSoup
- **Output**: Enhanced contact information with additional details and validation
- **Key Features**: Gap filling, fallback mechanisms, data merging and prioritization

### 4. Strategist Agent
- **Purpose**: Personalized outreach message generation
- **Technology**: Gemini LLM with market-specific prompts
- **Output**: Customized WhatsApp messages for each prospect
- **Key Features**: Personalization using extracted key facts, market-appropriate messaging

## Target Markets

1. **Student Recruitment Agencies**: Helping students find educational opportunities abroad
2. **Medical Tourism Agencies**: Connecting patients with international healthcare providers


# Project Structure

## Repository Layout

```
paperplane-omnichannel/
├── backend/              # Python FastAPI backend
│   ├── app/             # Main application code
│   └── requirements.txt # Python dependencies
├── documentation/        # Project documentation
└── .kiro/               # Kiro AI assistant configuration
```

## Backend Application Structure

The backend follows a layered architecture pattern with clear separation of concerns:

```
backend/app/
├── main.py                    # Application entry point, FastAPI app initialization
├── controller/                # HTTP request handlers (API endpoints)
│   ├── agents/               # AI agent endpoints
│   │   └── lead_gen_controller.py
│   ├── lead_profile/         # Lead/profile management endpoints
│   │   ├── generated_lead_controller.py
│   │   └── lead_profile_controller.py
│   └── twilio/               # Twilio webhook handlers
│       └── twilio_controller.py
├── service/                   # Business logic layer
│   ├── agents/               # AI agent orchestration
│   │   ├── scout/            # Scout agent module
│   │   │   ├── scout_agent.py        # Partner discovery via Google Maps
│   │   │   ├── scout_agent_helper.py # Google Maps scraping utilities
│   │   │   └── sample_response/      # Sample data for testing
│   │   ├── navigator/        # Navigator agent module
│   │   │   ├── navigator_agent.py           # Web crawling and contact extraction
│   │   │   ├── navigator_web_crawler.py     # V1 Crawl4AI web crawling utilities
│   │   │   ├── navigator_web_crawler_v2.py  # V2 systematic contact extraction
│   │   │   └── navigator_content_extractor.py # LLM-based content extraction
│   │   ├── lead_gen_service.py    # Pipeline orchestrator
│   │   ├── researcher_agent.py    # Contact enrichment and enhancement
│   │   └── strategist_agent.py    # Message drafting
│   └── lead_profile/         # Lead management services
│       ├── generated_lead_service.py
│       └── lead_profile_service.py
├── model/                     # Data models and schemas
│   ├── api/                  # API request/response models
│   │   ├── ppl_generated_lead.py
│   │   └── ppl_lead_profile.py
│   ├── lead_gen_model.py     # Lead generation data structures (includes PartnerContactDetails for V2)
│   └── outbound_message_model.py
└── util/                      # Shared utilities and configuration
    ├── agents/               # Agent configuration (ADK)
    │   └── adk_config.py
    ├── api/                  # Database configuration
    │   └── db_config.py
    ├── confluent/            # Kafka setup and helpers
    │   ├── confluent_config.py
    │   ├── confluent_helper.py
    │   ├── confluent_listener.py
    │   ├── lead_gen_listener.py
    │   └── lead_gen_producer.py
    └── twilio/               # Twilio configuration
        └── twilio_config.py
```

## Architectural Layers

### 1. Controllers (API Layer)
- Handle HTTP requests and responses
- Validate input using Pydantic models
- Trigger background tasks for long-running operations
- Return immediate responses with job IDs
- Located in: `app/controller/`

### 2. Services (Business Logic Layer)
- Orchestrate complex workflows
- Implement AI agent pipelines
- Coordinate between multiple components
- Handle error recovery and logging
- Located in: `app/service/`

### 3. Models (Data Layer)
- Define data structures using Pydantic
- Provide validation and serialization
- Separate API models from domain models
- Located in: `app/model/`

### 4. Utils (Infrastructure Layer)
- Configuration management
- External service clients (Kafka, Twilio)
- Shared helpers and utilities
- Located in: `app/util/`

## Key Conventions

### File Naming
- Use snake_case for all Python files
- Suffix pattern: `*_controller.py`, `*_service.py`, `*_model.py`, `*_config.py`
- Agent files: `*_agent.py` for individual agents, `*_agent_helper.py` for agent utilities
- Complex agents may have their own subdirectory (e.g., `scout/`) with multiple files

### Module Organization
- Each package has `__init__.py` for proper Python module structure
- Related functionality grouped in subdirectories
- Clear separation between agents, lead_profile, and twilio domains
- Complex agents (like scout and navigator) have dedicated subdirectories with:
  - Main agent file (`*_agent.py`) - Core business logic and LLM integration
  - Helper utilities (`*_agent_helper.py`, `*_web_crawler.py`) - Specialized scraping implementations
  - Content processing (`*_content_extractor.py`) - LLM-based data extraction
  - Sample data for testing (`sample_response/`) - Mock data for development

### Import Patterns
- Use absolute imports from `app.*`
- Example: `from app.service.agents.lead_gen_service import LeadGenPipeline`
- Configuration loaded via `python-dotenv` in entry points

### Logging
- Use Python's `logging` module
- Logger names follow module hierarchy: `lead_gen_pipeline.scout`
- Structured log messages with context (job_id, city, market, district, duration)
- Log levels: INFO for pipeline flow, DEBUG for detailed tracing, ERROR for failures
- Scout Agent includes scraping performance metrics and rate limiting logs

### API Routing
- All routes prefixed with `/api/ppl`
- Controllers use FastAPI APIRouter with tags
- Example: `/api/ppl/agents/lead-gen`, `/api/ppl/twilio/webhook`

### Background Tasks
- Long-running operations use `asyncio.create_task()`
- Kafka consumers run as background tasks in FastAPI lifespan
- Scout Agent uses async/await pattern for Google Maps scraping
- Navigator Agent uses async/await pattern for Crawl4AI web crawling
- Researcher and Strategist agents run in executor to avoid blocking event loop

## Data Models and Schema

### Navigator Agent V2 Data Models
- **PartnerContactDetails**: V2 contact schema with decision_maker, contact_info, contact_channel fields
- **PartnerEnrichment**: Enhanced with all_contacts field as List[PartnerContactDetails] for comprehensive contact data
- **Contact Channels**: Standardized enumeration (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)

### V2 Schema Format
```python
PartnerContactDetails:
  - decision_maker: str  # Name tied to contact information
  - contact_info: str    # Contact information (email, phone, social media URL)
  - contact_channel: str # Channel type (WhatsApp, Email, Messenger, Instagram, PhoneNo, Others)
```

## Configuration Files

- `.env` - Environment variables (not committed to git)
- `requirements.txt` - Python dependencies
- `.gitignore` - Excludes virtual environments, credentials, cache files
- `pyvenv.cfg` - Virtual environment configuration

## Agent Architecture Details

### Scout Agent Architecture
#### File Structure
- `scout_agent.py` - Main agent class with async discover_partners() method
- `scout_agent_helper.py` - Google Maps scraping utilities with Playwright
- Separation of concerns: business logic vs. scraping implementation

#### Data Flow
1. Generate market-specific search queries (city + district + market vertical)
2. Execute Google Maps scraping via Playwright (headless browser)
3. Extract structured business data (name, website, address, phone, reviews)
4. Return ScrapedBusinessData objects for Navigator Agent processing

#### Key Features
- **Async Implementation**: Non-blocking scraping operations
- **Rate Limiting**: Configurable delays between scrapes (10-30 seconds)
- **Anti-Detection**: Realistic user agent and browser behavior
- **Error Handling**: Graceful failure with partial results
- **Configurable Limits**: Adjustable result count per query

### Navigator Agent Architecture
#### File Structure
- `navigator_agent.py` - Main agent class with async navigate_and_extract_batch() method
- `navigator_web_crawler.py` - Original Crawl4AI web crawling utilities (V1)
- `navigator_web_crawler_v2.py` - V2 simplified systematic contact extraction implementation
- `navigator_content_extractor.py` - LLM-based content extraction and validation
- `navigator_llm_processor.py` - Gemini Flash integration for contact information structuring
- Separation of concerns: crawling vs. extraction vs. validation vs. LLM processing

#### V2 Implementation Components
- **NavigatorWebCrawlerV2**: Main crawler class with simplified systematic approach
- **ContactExtractor**: Specialized component for comprehensive contact information extraction
- **MarkdownGenerator**: Structured markdown generation following V2 schema specification
- **LLMProcessor**: Gemini Flash integration for structuring extracted contact information
- **PartnerContactDetails**: V2 contact schema with decision_maker, contact_info, contact_channel fields

#### V2 Data Flow
1. Receive ScrapedBusinessData objects from Scout Agent
2. Scan entire base page for links and contact information using NavigatorWebCrawlerV2
3. Discover navigation pages with header/footer prioritization (Contact > About > Team > Events)
4. Systematically crawl each navigation page extracting ALL contact information
5. Use ContactExtractor to extract emails, phone numbers, and social media handles with name association
6. Generate structured markdown using MarkdownGenerator with decision_maker/contact_info/contact_channel schema
7. Process markdown with LLMProcessor using Gemini Flash for structured extraction and validation
8. Return PartnerEnrichment objects with all_contacts field populated with validated PartnerContactDetails

#### Key V2 Features
- **Systematic Extraction**: No relevance filtering - extracts ALL contact information found
- **Header/Footer Navigation**: Prioritized navigation page discovery with fallback mechanisms
- **Comprehensive Contact Types**: Emails, phone numbers, social media handles (WhatsApp, Facebook, LinkedIn, Instagram)
- **Name Association**: Proximity-based analysis to associate names with contact information
- **Simplified Configuration**: Minimal Crawl4AI setup with basic browser configuration
- **Graceful Failure Handling**: Continues processing with partial results when individual pages fail
- **Structured Schema**: Consistent decision_maker/contact_info/contact_channel output format via PartnerContactDetails
- **LLM Integration**: Gemini Flash model with consistent temperature settings for reliable extraction
- **Validation & Fallback**: JSON parsing with regex-based fallback for malformed responses

## Documentation

- `documentation/` - Project documentation and diagrams
- `documentation/prompts/` - AI agent prompt templates
- `documentation/backup/` - Historical documentation


# Technology Stack

## Core Technologies

- **Language**: Python 3.10+
- **Web Framework**: FastAPI with async/await support
- **Event Streaming**: Confluent Kafka (cloud-hosted)
- **Messaging Provider**: Twilio (WhatsApp integration)
- **AI/ML Platform**: Google Cloud Vertex AI (Gemini models)
- **Database**: PostgreSQL (via asyncpg, SQLAlchemy)
- **Web Scraping**: Crawl4AI with Playwright for dynamic content

## Key Libraries & Frameworks

### Backend Core
- `fastapi` - Async web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation and settings management
- `python-dotenv` - Environment variable management

### Event Streaming
- `confluent-kafka` - Kafka client for event-driven architecture
- Topics: `whatsapp_inbound`, `whatsapp_outbound`, `lead_generated`

### AI & Agents
- `google-generativeai` - Gemini API integration
- `google-cloud-aiplatform` - Vertex AI services
- `litellm` - Multi-LLM abstraction layer
- `playwright` - Browser automation for Google Maps scraping
- `beautifulsoup4` - HTML parsing for web scraping
- `Crawl4AI` - Web scraping for lead research
- `nltk` - Natural language processing utilities

### External Integrations
- `twilio` - WhatsApp and SMS messaging
- `httpx` - Async HTTP client

### Development Tools
- `ngrok` - Local development tunneling for webhooks

## Common Commands

### Development Server
```bash
# Start FastAPI server with hot-reload
uvicorn app.main:app --reload

# Start from backend directory
cd backend
uvicorn app.main:app --reload
```

### Local Webhook Testing
```bash
# Expose local server for Twilio webhooks
ngrok http 8000
```

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

All configuration is managed via environment variables in `.env` files:

### Required Environment Variables
- `GCP_PROJECT_ID` - Google Cloud project identifier
- `GCP_REGION` - GCP region (e.g., us-central1)
- `KAFKA_BOOTSTRAP_SERVERS` - Confluent Kafka broker URL
- `KAFKA_API_KEY` - Kafka authentication key
- `KAFKA_API_SECRET` - Kafka authentication secret
- `TWILIO_ACCOUNT_SID` - Twilio account identifier
- `TWILIO_AUTH_TOKEN` - Twilio authentication token
- `TWILIO_NUMBER` - Twilio WhatsApp number (format: whatsapp:+14155238886)

### Optional Environment Variables
- `LOG_LEVEL` - Logging level (INFO or DEBUG)
- `LEAD_GEN_TIMEOUT` - Pipeline timeout in seconds (default: 300)
- `NAVIGATOR_TIMEOUT` - Navigator Agent timeout per entity in seconds (default: 180)
- `NAVIGATOR_PAGE_TIMEOUT` - Navigator Agent page timeout in seconds (default: 60 for V2, 90 for V1)
- `NAVIGATOR_MAX_RETRIES` - Navigator Agent max retry attempts (default: 3)
- `NAVIGATOR_CONCURRENT_LIMIT` - Navigator Agent concurrent crawl limit (default: 5)
- `NAVIGATOR_TEMPERATURE` - Navigator Agent LLM temperature (default: 0.1)
- `NAVIGATOR_V2_TEMPERATURE` - Navigator Agent V2 LLM temperature (default: 0.1)
- `NAVIGATOR_V2_MAX_TOKENS` - Navigator Agent V2 LLM max tokens (default: 2048)
- `CRAWL4AI_HEADLESS` - Crawl4AI headless browser mode (default: true)
- `CRAWL4AI_JAVASCRIPT` - Crawl4AI JavaScript execution (default: true for V2)
- `CRAWL4AI_STEALTH` - Crawl4AI stealth mode (default: true)

## Architecture Patterns

### Event-Driven Design
- All messaging flows through Kafka topics for decoupling
- Producers publish events, consumers process asynchronously
- Background tasks managed via FastAPI lifespan events
- Topics: `whatsapp_inbound`, `whatsapp_outbound`, `lead_generated`

### AI Agent Pipeline (ADK Pattern)
- Sequential agent orchestration: Scout → Navigator → Researcher → Strategist
- Async/await pattern throughout the pipeline for optimal performance
- Comprehensive logging at each pipeline stage with job_id tracking
- Timeout handling and partial result recovery
- Scout Agent: Discovers potential partners using Google Maps scraping with Playwright
- Navigator Agent: Extracts decision-maker contact information from partner websites using Crawl4AI
- Researcher Agent: Enhances Navigator enrichments with additional contact data and fallback information
- Strategist Agent: Generates personalized outreach messages
- Results published to `lead_generated` Kafka topic for downstream processing

### API Structure
- Controllers handle HTTP requests and validation
- Services contain business logic and orchestration
- Models define data structures (Pydantic)
- Utils provide shared configuration and helpers

## Development Workflow

### Running the Application
```bash
# From backend directory
cd backend
uvicorn app.main:app --reload
```

### Testing Webhooks Locally
```bash
# Expose local server for Twilio webhooks
ngrok http 8000
# Update Twilio webhook URL to: https://<ngrok-url>/api/ppl/twilio/webhook
```

### Database Operations
- Use SQLAlchemy models for database interactions
- Async operations via asyncpg
- Connection pooling managed by FastAPI lifespan

### Agent Implementation Details

#### Scout Agent Implementation
- **Data Source**: Google Maps business listings via Playwright automation
- **Search Strategy**: Market-specific queries (diagnostic centers, coaching centers, etc.)
- **Scraping Method**: Headless browser automation with anti-detection measures
- **Data Extraction**: Structured business data (name, website, address, phone, reviews)
- **Output**: Returns ScrapedBusinessData objects for Navigator Agent processing
- **Rate Limiting**: 10-30 second delays between scrapes to avoid detection
- **Async Pattern**: Fully async implementation for non-blocking pipeline execution

#### Navigator Agent Implementation
- **Purpose**: Systematic web crawling and comprehensive contact extraction
- **Technology**: Crawl4AI with Playwright for dynamic JavaScript content rendering
- **V2 Architecture**: Simplified systematic approach with NavigatorWebCrawlerV2 and ContactExtractor components
- **Navigation Strategy**: Header/footer prioritized navigation page discovery (Contact > About > Team > Events)
- **Content Processing**: Comprehensive contact extraction without relevance filtering
- **Contact Extraction**: Systematic extraction of emails, phone numbers, and social media handles with name association
- **LLM Integration**: Uses Gemini Flash model for structured contact information extraction
- **Output**: Returns PartnerEnrichment objects with all_contacts field containing comprehensive contact data
- **Timeout Handling**: 60-second page timeout with retry mechanisms and graceful failure handling

#### Researcher Agent Implementation
- **Purpose**: Enhances Navigator Agent results with additional enrichment and fallback data
- **Input**: Receives PartnerEnrichment objects from Navigator Agent
- **Enhancement Strategy**: Fills gaps in Navigator data using traditional web scraping methods
- **Fallback Mechanism**: Provides alternative contact extraction when Navigator results are incomplete
- **Data Merging**: Intelligently combines Navigator and fallback data, prioritizing Navigator results
- **Output**: Returns enhanced PartnerEnrichment objects for Strategist Agent

### Logging Best Practices
- Use structured logging with context (job_id, city, market, district)
- Logger naming: `module_name.component` (e.g., `lead_gen_pipeline.scout`, `lead_gen_pipeline.navigator`)
- Log levels: INFO for flow, DEBUG for details, ERROR for failures
- Include timing information for performance monitoring
- Scout Agent includes scraping performance metrics and rate limiting logs
- Navigator Agent includes web crawling metrics, LLM extraction timing, and retry attempt logs
- Navigator Agent V2 includes systematic contact extraction metrics and navigation page discovery logs
- LLMProcessor includes Gemini Flash processing metrics, JSON parsing validation, and fallback extraction logs
