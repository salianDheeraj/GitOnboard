# Team & Contribution Breakdown

This document details the roles, quantitative contributions (commits & lines of code), core architectural and engineering ownership, and individual contributions of all developers who have contributed to the **GitOnboard** platform.

---

## Project Status & Development Notice

> [!IMPORTANT]
> **Major Project Notice & Maintenance Mode:**
> - GitOnboard was developed as an academic **Final Year Major Project** and is **not planned for any commercial use**.
> - **Active feature development is complete.** There will not be any new major features or structural changes unless strictly required for academic project submission requirements or critical bug fixes.

---

## Quantitative Contribution Summary

*Metrics derived from Git commit history across repository lifecycle (`git log --numstat`):*

| Contributor | Role | Commits (%) | Lines Changed (%) | Lines Added | Lines Deleted |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Dheeraj Salian** | Project Creator, Lead Architect & Principal Engineer | **676 (96.85%)** | **566,390 (95.64%)** | 460,367 | 106,023 |
| **Sujal Ranjan** | Contributor | **20 (2.87%)** | **25,644 (4.33%)** | 20,050 | 5,594 |
| **Vedanta Verma** | Contributor | **2 (0.29%)** | **149 (0.03%)** | 105 | 44 |
| **Total** | | **698 (100%)** | **592,183 (100%)** | **480,522** | **111,661** |

---

## Authors & Contributors

### Dheeraj Salian
- **Role**: Project Creator, Lead Architect & Principal Engineer (AI, Systems & Research)
- **Email**: [dheerajsalian16@gmail.com](mailto:dheerajsalian16@gmail.com)
- **GitHub**: [@salianDheeraj](https://github.com/salianDheeraj)
- **Commit Contribution**: 96.85% (676 commits)
- **Code Contribution**: 95.64% of total lines changed (460,367 lines added)
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
- **Commit Contribution**: 2.87% (20 commits)
- **Code Contribution**: 4.33% of total lines changed (20,050 lines added)
- **Key Contributions**:
  - **In-Browser Terminal & Sandbox Host Execution**: Interactive shell and pseudo-terminal (PTY) session management (`backend/services/pty_session.py`, `backend/routers/sandbox.py`) and browser xterm.js terminal integration.
  - **Worktree Provisioning & Cleanup**: Worktree provisioning service for isolated sandbox execution (`backend/services/worktree_provisioner.py`) and repository disk state cleanup (`backend/services/repo_cleanup.py`).
  - **Code Verification & Repair Pipeline Prototype**: Static/dynamic code verifier orchestrator and repair harness (`backend/verification/`, `backend/routers/verification_pipeline.py`).
  - **Workspace UI Shell**: Multi-panel IDE layout shell (dock container, editor, and file tree UI components).
  - **UI Enhancements**: Theme toggle switching provider and minor navigation adjustments.

---

### Vedanta Verma
- **Role**: Contributor
- **Email**: [vedantverma2005@gmail.com](mailto:vedantverma2005@gmail.com)
- **Commit Contribution**: 0.29% (2 commits)
- **Code Contribution**: 0.03% of total lines changed (105 lines added)
- **Key Contributions**:
  - **Authentication Routing**: Fixes to authentication routing and proxy cookie handling (`backend/routers/auth.py`, `frontend/proxy.ts`).
  - **UI Tweaks**: Minor styling adjustments to the global search bar input and dashboard layout.

---

## Rights & Licensing Scope

For full licensing details and commercial usage inquiries, refer to the [License & Commercial Use](README.md#license--commercial-use) section in `README.md` and [LICENSE](LICENSE).

- **Core Platform, Architecture & All Unlisted Features**: Exclusively owned, copyrighted, and reserved by **Dheeraj Salian**. No third party or contributor may commercialize, sublicense, or relicense the core platform or its architecture without prior written authorization from Dheeraj Salian.
- **Module-Specific Contributor Rights**:
  - **Sujal Ranjan**: Commercial usage, licensing, or extraction of the sandbox PTY terminal, worktree provisioning, or verification orchestrator code requires written permission from Sujal Ranjan.
  - **Vedanta Verma**: Commercial usage or licensing of specific auth routing and search bar UI contributions requires written permission from Vedanta Verma.
- **Mutual Boundary**: No individual developer or contributor has rights to commercialize or license work created by another developer. All commercial rights remain strictly tied to the original author of each respective module.

