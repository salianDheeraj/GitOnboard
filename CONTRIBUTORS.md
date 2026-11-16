# Team & Contribution Breakdown

This document details the roles, core architectural and engineering ownership, and individual contributions of all developers who have contributed to the **GitOnboard** platform.

---

## Authors & Contributors

### Dheeraj Salian
- **Role**: Project Creator, Lead Architect & Principal Engineer (AI, Systems & Research)
- **Email**: [dheerajsalian16@gmail.com](mailto:dheerajsalian16@gmail.com)
- **GitHub**: [@salianDheeraj](https://github.com/salianDheeraj)
- **Key Contributions**:
  - **Core Code Intelligence**: Multi-language Tree-sitter CST parsing, symbol resolution, relational Fact Store (Layer 4), RIM graph construction, and deterministic call/dependency graph algorithms.
  - **Information Retrieval & Search**: Hybrid search engine combining BM25 keyword index, ChromaDB vector embeddings, bounded multi-hop graph traversal, and staleness/rebuild detection pipelines.
  - **AI Systems & Orchestration**: Multi-agent investigation pipeline (planner/worker orchestration, agent inspector, dynamic timeline, tool calling guards), LLM provider integrations (Ollama local runtimes, Groq, OpenRouter), token budget gating, telemetry calibration, and context compaction.
  - **Interactive Visualizations & Frontend**: Sigma.js canvas with ForceAtlas2 physics simulation, elastic spring drag, high-contrast dependency/architecture explorers, and Aurora glass design system.
  - **Empirical Research & Benchmarking**: Pilot benchmarks, three-condition ablation isolation, multi-run root-cause investigation protocols, and automated evaluation runners.
  - **Infrastructure & Platform Security**: GitHub OAuth, user data isolation, private repo ingestion, Docker Compose orchestration, PostgreSQL migrations, and Azure/Azurite multi-phase blob storage lifecycle.

---

### Sujal Ranjan
- **Role**: Contributor
- **Email**: [sujalranjan02@gmail.com](mailto:sujalranjan02@gmail.com)
- **GitHub**: [@Sujalranjan](https://github.com/Sujalranjan)
- **Key Contributions**:
  - **In-Browser Terminal & Sandbox Host Execution**: Interactive shell and pseudo-terminal (PTY) session management (`backend/services/pty_session.py`, `backend/routers/sandbox.py`) and browser xterm.js terminal panel.
  - **Worktree Provisioning & Cleanup**: Worktree provisioning service for isolated execution (`backend/services/worktree_provisioner.py`) and repository disk state cleanup (`backend/services/repo_cleanup.py`).
  - **Workspace UI Shell**: Multi-panel IDE layout shell (dock container, editor, and file tree UI components).
  - **UI Enhancements**: Theme toggle switching provider and minor navigation adjustments.

---

### Vedanta Verma
- **Role**: Contributor
- **Email**: [vedantverma2005@gmail.com](mailto:vedantverma2005@gmail.com)
- **Key Contributions**:
  - **Authentication Routing**: Fixes to authentication routing and proxy cookie handling (`backend/routers/auth.py`, `frontend/proxy.ts`).
  - **UI Tweaks**: Minor styling adjustments to the global search bar input and dashboard layout.

---

## Rights & Licensing Scope

For full licensing details and commercial usage inquiries, refer to the [License & Commercial Use](README.md#license--commercial-use) section in `README.md` and [LICENSE](LICENSE).

- **General Platform, Architecture & Core Rights**: Exclusively owned and reserved by **Dheeraj Salian**.
- **Module-Specific Feature Permissions**: Contact **Sujal Ranjan** (for sandbox PTY terminal and worktree provisioning modules) or **Vedanta Verma** (for specific auth routing tweaks) regarding permissions for their individual module contributions.
