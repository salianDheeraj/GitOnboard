# GitOnBoard - Repository Intelligence Platform

An advanced code analysis and intelligence platform that ingests GitHub repositories, builds deterministic abstract syntax trees and knowledge graphs, detects architectural capabilities, and provides semantic search and interactive visualization.

---

## Quick Start (5 minutes)

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ & npm
- Python 3.10+ with `uv`

### Start the Platform

```bash
# Start backend, database, and storage
docker compose up --build -d

# Start frontend (in a new terminal)
cd frontend
npm install
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs: http://localhost:8000/docs)
- Database UI: http://localhost:5050 (pgAdmin)

For detailed setup, environment configuration, and troubleshooting, see [Development Guide](docs/guides/DEVELOPMENT.md).

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (Python 3.10+), Uvicorn |
| **Frontend** | Next.js 16, React 19, TypeScript |
| **Database** | PostgreSQL 15 (SQLAlchemy ORM) |
| **Storage** | Azure Blob / Azurite |
| **Analysis** | Tree-sitter (multi-language AST parsing) |
| **Containers** | Docker & Docker Compose |

---

## Documentation

- **[Project Structure](PROJECT_STRUCTURE.md)** — Directory layout and file organization
- **[Architecture](docs/architecture/ARCHITECTURE.md)** — System design and pipeline flow
- **[Data Model](docs/architecture/DATA_MODEL.md)** — Database schema and relationships
- **[Development](docs/guides/DEVELOPMENT.md)** — Detailed setup and development workflow
- **[Testing](docs/guides/TESTING.md)** — Test suites and verification
- **[Full Documentation Index](docs/README.md)** — Complete guide to all documentation

---

## Project Guidelines

This is a college-level Final Year Major Project. See [CLAUDE.md](CLAUDE.md) for engineering principles and architectural constraints.

> **Project Status & Maintenance Notice:** Active development for this project is concluded and it is not intended for commercialization. No further major changes or new features are planned unless explicitly required for academic submission criteria or critical bug fixes.

**Key Rules:**
- Backend and database run in Docker Compose (PostgreSQL only — no SQLite)
- All code follows deterministic, inspectable patterns
- Documentation is kept simple and aligned with actual implementation

---

## Team & Authors

| Name | Role | Commits (%) | Code Contribution (%) | Email |
|------|------|:-----------:|:---------------------:|-------|
| **Dheeraj Salian** | Project Creator, Lead Architect & Principal Engineer | **676 (96.85%)** | **566,390 lines (95.64%)** | [dheerajsalian16@gmail.com](mailto:dheerajsalian16@gmail.com) |
| **Sujal Ranjan** | Contributor | **20 (2.87%)** | **25,644 lines (4.33%)** | [sujalranjan02@gmail.com](mailto:sujalranjan02@gmail.com) |
| **Vedanta Verma** | Contributor | **2 (0.29%)** | **149 lines (0.03%)** | [vedantverma2005@gmail.com](mailto:vedantverma2005@gmail.com) |

> For detailed role descriptions, architectural ownership, and a comprehensive breakdown of individual contributions, see **[CONTRIBUTORS.md](CONTRIBUTORS.md)**.

---

## License & Commercial Use

GitOnboard is licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

- **Noncommercial & Educational Use:** GitOnboard is freely available for qualifying educational, academic, personal, hobby, and other noncommercial purposes (such as learning, teaching, experimentation, and research).
- **Commercial Use & Feature Licensing Restrictions:** Commercial use is **strictly not permitted** without separate, prior written authorization:
  - **Overall Project, Core Architecture & All Other Features:** All core rights remain exclusively with **Dheeraj Salian**. Prior written permission must be obtained from Dheeraj Salian for commercial use or licensing of the platform and its core codebase.
  - **Module-Specific Contributions:** Commercial rights for specific contributed modules remain strictly with the respective developer who built them. For commercial usage, licensing, or integration of individual modules (e.g., sandbox PTY terminal, worktree provisioning, or verification pipeline by Sujal Ranjan; or specific authentication routing tweaks by Vedanta Verma), inquiries and permissions must be directed to that contributor.
  - **Mutual Commercialization Boundary:** No contributor or third party may commercialize or license features or modules created by another developer.
- **Public Availability:** The public availability of this repository on GitHub does not grant commercial rights or licenses.
- **Inquiries & Permissions:**
  - **General, Core Platform & Architecture Licensing:** Contact project owner **Dheeraj Salian** via GitHub: [https://github.com/salianDheeraj](https://github.com/salianDheeraj) or email: [dheerajsalian16@gmail.com](mailto:dheerajsalian16@gmail.com).
  - **Sujal Ranjan (Sandbox Terminal / Worktree / Verification Modules):** [sujalranjan02@gmail.com](mailto:sujalranjan02@gmail.com)
  - **Vedanta Verma (Auth / Search Bar Modules):** [vedantverma2005@gmail.com](mailto:vedantverma2005@gmail.com)

