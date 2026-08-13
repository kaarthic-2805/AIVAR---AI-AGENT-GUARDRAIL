# 🛡️ EstateGuard AI

### Action-Governed Multi-Agent AI Platform

EstateGuard AI is a **production-oriented AI governance platform** designed to control, monitor, and secure AI agents before they execute external actions.

Unlike traditional guardrails that primarily inspect user prompts and LLM responses, EstateGuard AI focuses on **action-level governance**. Every agent action is intercepted by an Action Dispatcher and evaluated against configurable policies before the requested tool or service is executed.

Sensitive actions can be paused for **Human-in-the-Loop (HITL)** approval, while all important governance decisions can be persisted for auditing and traceability.

---

## 🔗 Live Deployment

| Resource                         | Link                                   
| -------------------------------- | -------------------------------------- 
| 🚀 **Deployed Application/API**  |   http://44.204.130.149:8000/
| 📚 **Swagger API Documentation** |   http://44.204.130.149:8000/docs      
| ❤️ **Health Check**              |   http://44.204.130.149:8000/health      
| 📖 **OpenAPI Schema**            |   http://44.204.130.149:8000/openapi.json

> **Production deployment:** EstateGuard AI is deployed in a cloud environment to demonstrate its ability to govern real AI workloads through an externally accessible API rather than operating only on localhost.

---

# 1. Problem Statement

## Context

As AI systems evolve from simple chatbots into autonomous agents, they are increasingly capable of performing actions such as:

* Calling external APIs
* Searching the web
* Accessing databases
* Executing tools
* Retrieving enterprise information
* Triggering downstream services
* Performing automated workflows

Traditional LLM guardrails primarily focus on **input validation and output filtering**.

However, an AI agent can generate a perfectly valid response while simultaneously attempting to perform an unsafe or unauthorized action through a connected tool.

For example:

```text
User
  ↓
AI Agent
  ↓
"Search the web"
  ↓
Tool Execution
```

If the agent is allowed to directly invoke the tool, there may be no centralized governance layer controlling that action.

EstateGuard AI addresses this problem by introducing an **action-level governance layer** between AI agents and their external tools.

---

# 2. The Challenge

### Build a production-ready AI governance platform that intercepts, evaluates, and controls actions performed by AI agents before those actions reach external tools or services.

EstateGuard AI ensures that AI agents cannot directly execute governed actions without first passing through the policy enforcement layer.

---

# 3. What EstateGuard AI Builds

EstateGuard AI provides:

* Multi-agent AI orchestration
* Centralized action interception
* Policy-based action evaluation
* Allow/Block decisions
* Human-in-the-Loop approval
* MCP-based tool integration
* Real LLM integration
* Persistent state
* Audit logging
* REST APIs
* Health monitoring
* Cloud deployment
* API documentation through Swagger/OpenAPI
* Error handling and controlled execution

---

# 4. Core Architecture

```text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   FastAPI API    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ LangGraph        │
                         │ Supervisor       │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
             ┌──────────────┐           ┌──────────────┐
             │ Research /   │           │ Other        │
             │ Specialized  │           │ Agents       │
             │ Agent        │           │              │
             └──────┬───────┘           └──────┬───────┘
                    │                          │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │  Action Dispatcher  │
                      └──────────┬──────────┘
                                 │
                                 ▼
                      ┌─────────────────────┐
                      │    Policy Engine    │
                      └──────────┬──────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             │                   │                    │
             ▼                   ▼                    ▼
          ┌───────┐          ┌────────┐        ┌─────────────┐
          │ ALLOW │          │ BLOCK  │        │ REQUIRE HITL│
          └───┬───┘          └────────┘        └──────┬──────┘
              │                                       │
              │                                ┌──────▼──────┐
              │                                │   Human     │
              │                                │   Approval  │
              │                                └──────┬──────┘
              │                                       │
              └───────────────────┬───────────────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │      MCP Layer      │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │ External Tools/APIs │
                       │ Web Search / etc.   │
                       └─────────────────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │    PostgreSQL DB    │
                       │ State + Audit Logs  │
                       └─────────────────────┘
```

---

# 5. Request Execution Flow

## Step 1 — User Request

A user submits a request through the EstateGuard AI API.

```text
POST /api/...
```

---

## Step 2 — Supervisor Routing

The LangGraph supervisor analyzes the request and determines which specialized agent should process it.

---

## Step 3 — Agent Reasoning

The selected agent determines whether an external tool or action is required.

For example:

```text
"Search the latest information about AWS Bedrock."
```

The research agent may determine that a web search tool is required.

---

## Step 4 — Action Interception

The agent does **not directly execute the tool**.

Instead, the requested action is sent to the:

```text
Action Dispatcher
```

This creates a centralized enforcement point for agent actions.

---

# 6. Policy Engine

The Policy Engine evaluates every governed action against predefined rules.

The platform supports decisions such as:

### ALLOW

The action satisfies the configured policies.

```text
Action → Policy Engine → ALLOW → Execute Tool
```

### BLOCK

The action violates a policy.

```text
Action → Policy Engine → BLOCK → Stop Execution
```

### REQUIRE_HITL

The action requires human authorization.

```text
Action
  ↓
Policy Engine
  ↓
REQUIRE_HITL
  ↓
Human Approval
  ↓
Approve / Reject
```

### LOG_AND_ALLOW

The action is allowed while the governance event is recorded for auditing.

---

# 7. Human-in-the-Loop

EstateGuard AI supports Human-in-the-Loop governance for actions that require additional authorization.

The workflow becomes:

```text
Agent
  ↓
Action Dispatcher
  ↓
Policy Engine
  ↓
REQUIRE_HITL
  ↓
Human Reviewer
  ↓
┌───────────────┐
│               │
▼               ▼
APPROVE       REJECT
│               │
▼               ▼
Execute       Block
```

This allows organizations to retain human control over sensitive agent actions.

---

# 8. MCP Integration

EstateGuard AI integrates external tools through the **Model Context Protocol (MCP)**.

MCP provides a standardized interface between AI agents and external tools.

For example:

```text
Research Agent
      ↓
Action Dispatcher
      ↓
Policy Engine
      ↓
ALLOW
      ↓
MCP
      ↓
Tavily Search
      ↓
Search Result
      ↓
Agent
```

This architecture allows additional tools to be integrated without significantly changing the core governance layer.

---

# 9. Technology Stack

| Category             | Technology                      |
| -------------------- | ------------------------------- |
| Programming Language | Python                          |
| Backend Framework    | FastAPI                         |
| AI Orchestration     | LangGraph                       |
| Agent Architecture   | Supervisor + Specialized Agents |
| LLM                  | Configurable real LLM provider  |
| Tool Protocol        | MCP                             |
| Web Search           | Tavily MCP                      |
| Database             | PostgreSQL                      |
| API Documentation    | Swagger / OpenAPI               |
| Deployment           | AWS                             |
| Containerization     | Docker                          |
| State Persistence    | PostgreSQL                      |
| Governance           | Policy Engine                   |
| Human Approval       | HITL                            |
| Logging              | Application + Governance Logs   |

---

# 10. Production Readiness

EstateGuard AI is designed according to the production-readiness requirements of the challenge.

## ☁️ Cloud Deployment

The application is deployed to an AWS environment rather than being limited to localhost.

```text
Client
  ↓
AWS
  ↓
EstateGuard AI API
  ↓
AI Agent Workflow
  ↓
Policy Enforcement
  ↓
MCP Tools
```

This demonstrates that the governance platform can be exposed as an enterprise-accessible service.

---

## 🔄 Concurrent API Requests

FastAPI provides an asynchronous API layer capable of handling multiple API requests.

The application architecture separates:

* API handling
* Agent orchestration
* Policy evaluation
* Tool execution
* Database persistence

This makes the system suitable for handling multiple AI-agent workflows rather than operating as a single standalone script.

---

## 💾 Persistent State

PostgreSQL provides persistent storage for application and governance data.

Persistent information can include:

* Requests
* Agent execution state
* Action requests
* Policy decisions
* HITL decisions
* Tool execution information
* Audit records

This ensures that important governance information is not lost when the application restarts.

---

## 📝 Logging

EstateGuard AI maintains logs for important application and governance events.

Example:

```text
REQUEST_RECEIVED
      ↓
AGENT_SELECTED
      ↓
ACTION_REQUESTED
      ↓
POLICY_EVALUATED
      ↓
ACTION_ALLOWED
      ↓
TOOL_EXECUTED
      ↓
RESULT_RECEIVED
```

For blocked or HITL actions:

```text
ACTION_REQUESTED
      ↓
POLICY_EVALUATED
      ↓
REQUIRE_HITL
      ↓
HUMAN_APPROVAL
      ↓
APPROVED / REJECTED
```

These logs improve troubleshooting, monitoring, security analysis, and auditability.

---

# 11. Health Check

EstateGuard AI exposes a health-check endpoint for monitoring application availability.

```http
GET /health
```

Production URL:

`<YOUR_DEPLOYED_AWS_URL>/health`

Expected response:

```json
{
  "status": "healthy"
}
```

The health endpoint can be used by:

* AWS monitoring
* Load balancers
* Deployment pipelines
* Monitoring systems
* Operations teams

---

# 12. Swagger API Documentation

EstateGuard AI exposes interactive API documentation using FastAPI's Swagger/OpenAPI integration.

Swagger:

http://44.204.130.149:8000/docs

OpenAPI specification:

http://44.204.130.149:8000/openapi.json

Swagger allows developers and evaluators to:

* View available APIs
* Inspect request parameters
* Test endpoints
* View response schemas
* Test the deployed service without installing the application locally

---

# 13. API Usage

After deployment, the API can be accessed through the deployed URL.

Example:

```bash
curl <YOUR_DEPLOYED_AWS_URL>/health
```

For API endpoints, use the Swagger interface:

```text
<YOUR_DEPLOYED_AWS_URL>/docs
```

The Swagger UI provides the exact request and response schemas supported by the deployed version.

---

# 14. Local Installation

## Prerequisites

Install:

* Python 3.11+
* Docker
* PostgreSQL
* Git
* Required LLM API credentials
* Required MCP/tool credentials

---

## Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>

cd EstateGuard-AI
```

---

## Create Virtual Environment

### Windows

```bash
python -m venv venv

venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 15. Environment Variables

Create a `.env` file.

Example:

```env
DATABASE_URL=<POSTGRESQL_CONNECTION_STRING>

LLM_API_KEY=<YOUR_LLM_API_KEY>

TAVILY_API_KEY=<YOUR_TAVILY_API_KEY>

ENVIRONMENT=production
```

> Never commit `.env` files or API keys to GitHub.

Use:

```text
.env
```

in `.gitignore`.

---

# 16. Run Locally

Start the FastAPI application:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The application will be available at:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

---

# 17. Docker Deployment

Build the Docker image:

```bash
docker build -t estateguard-ai .
```

Run the container:

```bash
docker run -p 8000:8000 \
  --env-file .env \
  estateguard-ai
```

Check the application:

```bash
curl http://localhost:8000/health
```

---

# 18. AWS Deployment

EstateGuard AI can be deployed as a containerized FastAPI service in AWS.

High-level deployment:

```text
Developer
    │
    ▼
GitHub
    │
    ▼
Docker Image
    │
    ▼
AWS Container Infrastructure
    │
    ▼
EstateGuard AI
    │
    ├── FastAPI
    ├── LangGraph
    ├── Policy Engine
    ├── MCP
    └── LLM
            │
            ▼
       PostgreSQL
```

The deployment separates the application runtime from persistent database storage and external AI/tool services.

---

# 19. Security and Governance

EstateGuard AI follows a **deny-by-default governance philosophy for sensitive actions**.

Important security principles include:

* Centralized action interception
* Policy-based authorization
* Human approval for sensitive operations
* Environment-based secrets
* No hardcoded API credentials
* Persistent audit information
* Controlled tool access
* Error handling
* Health monitoring
* API-level access to the governance system

The goal is to ensure that an AI agent cannot bypass the governance layer by directly invoking an external tool.

---

# 20. Success Criteria

EstateGuard AI satisfies the core production-readiness goals by providing:

| Requirement               | EstateGuard AI                    |
| ------------------------- | --------------------------------- |
| Cloud deployment          | ✅ AWS deployment                  |
| Usable API                | ✅ FastAPI REST API                |
| API documentation         | ✅ Swagger/OpenAPI                 |
| Health check              | ✅ `/health`                       |
| Agent orchestration       | ✅ LangGraph                       |
| Multi-agent workflow      | ✅ Supervisor + specialized agents |
| Action governance         | ✅ Action Dispatcher               |
| Policy enforcement        | ✅ Policy Engine                   |
| Block actions             | ✅ Supported                       |
| Allow actions             | ✅ Supported                       |
| Human approval            | ✅ HITL                            |
| External tool integration | ✅ MCP                             |
| Web search integration    | ✅ Tavily MCP                      |
| Persistent state          | ✅ PostgreSQL                      |
| Logging                   | ✅ Application/Governance logging  |
| Containerization          | ✅ Docker                          |
| Real AI integration       | ✅ Configurable LLM provider       |
| Production API            | ✅ Cloud-accessible API            |

---

# 21. Key Differentiator

The primary differentiator of EstateGuard AI is:

> **"Govern the actions of AI agents, not just their responses."**

Traditional guardrails:

```text
User
 ↓
LLM
 ↓
Output Guardrail
 ↓
Response
```

EstateGuard AI:

```text
User
 ↓
Supervisor
 ↓
Agent
 ↓
Action
 ↓
Action Dispatcher
 ↓
Policy Engine
 ↓
ALLOW / BLOCK / HITL
 ↓
MCP Tool
 ↓
Result
```

This makes EstateGuard AI suitable for environments where AI agents are expected to interact with real systems and external tools.

---

# 22. Enterprise Integration

EstateGuard AI is designed as a governance layer that can be positioned between enterprise AI agents and their tool ecosystem.

```text
                  Enterprise AI Stack

       ┌──────────────────────────────┐
       │        AI Applications       │
       └───────────────┬──────────────┘
                       │
                       ▼
       ┌──────────────────────────────┐
       │       AI Agents / LLMs       │
       └───────────────┬──────────────┘
                       │
                       ▼
       ┌──────────────────────────────┐
       │      EstateGuard AI          │
       │                              │
       │  Policy + Action Governance  │
       │  HITL + Audit + Monitoring   │
       └───────────────┬──────────────┘
                       │
                       ▼
       ┌──────────────────────────────┐
       │       MCP / Tool Layer       │
       └───────────────┬──────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Search        APIs       Enterprise
                                Services
```

This architecture allows EstateGuard AI to act as a reusable governance layer rather than being tightly coupled to a single AI application.

---

# 23. Future Enhancements

Potential future improvements include:

* Role-Based Access Control (RBAC)
* Policy management dashboard
* Advanced audit analytics
* Agent risk scoring
* Rate limiting
* JWT/OAuth authentication
* AWS CloudWatch integration
* AWS Bedrock integration
* AWS ECS/EKS deployment
* Redis-based distributed state
* Policy versioning
* Enterprise SSO
* Real-time governance dashboard
* Multi-tenant governance
* Advanced threat detection
* Compliance reporting

---

# 24. Project Structure

```text
EstateGuard-AI/
│
├── backend/
│   ├── agents/
│   ├── graph/
│   ├── guardrails/
│   ├── policy/
│   ├── mcp/
│   ├── api/
│   ├── models/
│   └── services/
│
├── frontend/
│
├── database/
│   └── schema.sql
│
├── tests/
│
├── Dockerfile
├── requirements.txt
├── .env.example
├── main.py
└── README.md
```

> Update the project structure above to exactly match the final repository structure before submission.

---

# 25. Conclusion

EstateGuard AI demonstrates a production-oriented approach to **AI agent governance and action security**.

The platform combines:

**Multi-Agent AI + LangGraph + Policy Enforcement + Action Guardrails + MCP + HITL + PostgreSQL + FastAPI + Docker + AWS**

to create a controlled execution environment for autonomous AI agents.

Rather than trusting an AI agent to safely execute every action it generates, EstateGuard AI introduces a centralized governance layer that evaluates actions **before they reach external tools**.

This architecture enables organizations to adopt agentic AI while maintaining **control, security, transparency, auditability, and human oversight**.

---

## 🔗 Important Links

**Live API:**
http://44.204.130.149:8000/

**Swagger:**
http://44.204.130.149:8000/docs

**Health Check:**
http://44.204.130.149:8000/health

**OpenAPI:**
http://44.204.130.149:8000/openapi.json

**GitHub Repository:**
https://github.com/kaarthic-2805/AIVAR---AI-AGENT-GUARDRAIL.git
