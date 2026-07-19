<div align="center">

# 🛡️ NexGuard

### AI-Powered Security Operations Platform

**_Detect Faster. Investigate Smarter. Respond with Confidence._**

</div>

---

NexGuard is a local-first, privacy-preserving Security Operations platform that
helps SOC analysts cut through alert fatigue. It combines a layered anomaly
detection stack (DeepLog-style sequence models + Isolation Forest + an ensemble),
explainable-by-construction alerts, a **local** LLM triage copilot that drafts
analyst-ready incident reports, and a hallucination-verification gate that refuses
to let the copilot fabricate evidence. An analyst feedback loop turns corrections
into measurable precision/recall gains.

> **Status:** 🚧 Under active construction — built vertical-slice-first, phase by
> phase. See [`docs/architecture/build-plan.md`](docs/architecture/build-plan.md)
> for the roadmap and current checkpoint.

## Documentation

- **Architecture:** [`docs/architecture/README.md`](docs/architecture/README.md)
- **Detection pipeline:** [`docs/architecture/detection-pipeline.md`](docs/architecture/detection-pipeline.md)
- **Data model:** [`docs/architecture/data-model.md`](docs/architecture/data-model.md)
- **Design spec:** [`docs/superpowers/specs/2026-07-19-nexguard-design.md`](docs/superpowers/specs/2026-07-19-nexguard-design.md)
- **Decision records:** [`docs/architecture/adr/`](docs/architecture/adr)

## Tech stack

**Backend/ML** · Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic ·
PyTorch · scikit-learn · Drain3 · Ollama · MLflow · Redis · PostgreSQL

**Frontend** · Next.js 15 · React 19 · TypeScript · Tailwind v4 · shadcn/ui ·
TanStack Query · Framer Motion · Recharts

**DevOps** · Docker · Docker Compose · GitHub Actions · pre-commit

<!-- Installation, usage, benchmarks, screenshots, limitations, and roadmap will
be filled in as phases complete. -->
