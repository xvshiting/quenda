# Quenda Glossary

This document establishes the ubiquitous language for the Quenda project.

---

## Core Concepts

### Agent

An agent is the core abstraction that orchestrates LLM interactions with tools.

- **In code**: `Agent` class in `quenda.runtime`
- **Examples**: QA agent, coding agent, legal research agent

### Session

A session represents a conversation with an agent, managing message history and state.

- **In code**: `Session` class in `quenda.runtime`
- **Examples**: Current conversation with Quenda Code

### Tool

A tool is a capability the agent can invoke during execution.

- **In code**: `@tool` decorator, `ToolSpec` in `quenda.kernel`
- **Examples**: `read_file`, `run_shell`, `search_entities`

### Skill

A skill is a composable capability package with instructions and resources.

- **In code**: `SKILL.md` in `skills/` directory
- **Examples**: `playwright`, `pdf`, `code-review`, `legal-analysis`

### Provider

A provider is a connection to an LLM service (OpenAI, Anthropic, DeepSeek, etc.).

- **In code**: `ProviderSpec` in `quenda.providers`
- **Examples**: `openai`, `anthropic`, `deepseek`, `jdcloud`

### Workspace

The workspace is the security boundary for file operations and tool execution.

- **In code**: `workspace` parameter in tools
- **Examples**: `/Users/xushiting/Workspace/lawnet`

---

## Architecture Layers

### Kernel

The synchronous core that handles model-tool loops. No knowledge of agents, sessions, or users.

- **Responsibility**: Execute tool calls, manage conversation turns
- **Testability**: Fully testable with fake models

### Runtime

The async layer that manages Agent/Session/Run lifecycle and event emission.

- **Responsibility**: Session management, context handling, event streaming

### Host

The layer that handles persistence, identity, permissions, and instruction composition.

- **Responsibility**: User management, workspace binding, skill activation

### Interface

The layer that renders events and handles user interaction (REPL, CLI).

- **Responsibility**: Display, user input, command processing

---

## Enterprise Concepts

### Permission Control

The ability to restrict which users can access which agents and data.

- **Status**: Planned
- **Use case**: Law firm restricts junior lawyers from client contracts

### Data Isolation

The ability to separate data between tenants or projects.

- **Status**: Planned
- **Use case**: Multiple law firms on same deployment, data completely isolated

### Private Deployment

The ability to run Quenda entirely on-premise with no external dependencies.

- **Status**: Partial (requires configuration)
- **Use case**: Law firm with strict data sovereignty requirements

---

## Legal Domain Concepts

### Legal Graph System

A knowledge graph built from legal documents (court decisions, contracts, laws).

- **Implementation**: Lawnet project
- **Components**: Entities (plaintiff, defendant, law), relationships, notes

### Legal QA Agent

An agent that answers questions about legal documents using the legal graph.

- **Tools**: `search_entities`, `get_entity_detail`, `search_documents`
- **Use case**: "What are the key arguments in this case?"

### Document Analysis

The process of extracting entities and relationships from legal documents.

- **Output**: Markdown notes with bidirectional links
- **Storage**: `vault/` directory structure

---

## Positioning Concepts

### Minimal API

The design principle that the core API should be as simple as possible.

- **Manifestation**: `Agent`, `Session`, `@tool` — that's it
- **Contrast**: LangChain has 100+ abstractions

### Testable Architecture

The design principle that every layer should be independently testable.

- **Manifestation**: Kernel can be tested with fake models, no network needed
- **Contrast**: Many frameworks require real API calls to test

### Pluggable Enterprise Features

The design principle that enterprise features should be optional modules, not core.

- **Manifestation**: Permission control as a plugin, not built-in
- **Contrast**: Enterprise frameworks bundle everything

---

## Anti-Patterns (What We Don't Do)

### Multi-Agent Orchestration

Coordinating multiple agents in complex workflows.

- **Why not**: Violates simplicity principle
- **Who does it**: CrewAI, AutoGen

### Workflow Engine

Visual or code-based workflow builders for agent pipelines.

- **Why not**: Violates simplicity principle
- **Who does it**: LangGraph, n8n

### Universal Tools

Tools that work across all industries without specialization.

- **Why not**: We focus on legal-first
- **Who does it**: LangChain (hundreds of generic integrations)
