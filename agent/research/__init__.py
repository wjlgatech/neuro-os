"""
``agent.research`` — research vertical (one of three on the domain_app
substrate).

Audience: researchers who want to convert paper-collecting into
recursive world-model refinement.

Built per ``docs/prd/enhanced_research_prd.md`` with the Phase 0
sharpenings:

* 4 first-class metrics (not 10):
  - mechanism_extraction_rate (`MechanismCard count / paper bookmarks`)
  - assumption_extraction_rate (`assumptions extracted / paper`)
  - prediction_accuracy (`correct predictions / total predictions`)
  - thesis_continuity_score (`days on the load-bearing thesis`)
* 6 named failure modes (substrate-enforced):
  paper_collector, topic_hopper, memorizer, authority_acceptor,
  overloaded, forgetting.
* Iterations on a thesis are formally counted as ``MechanismCard``
  revisions OR ``PredictionLog`` entries citing the thesis.
* Privacy: notes default-private to research per
  ``cross_vertical.write_note`` default. Researchers explicitly opt
  into sharing mechanism cards with investment / startup.
"""
from __future__ import annotations

from agent.research.briefs import (
    DecisionBrief,
    ProjectContext,
    QuestionForCollaborator,
    generate_brief,
    render_markdown as render_brief_markdown,
)
from agent.research.catalog import RESEARCH_CATALOG
from agent.research.checkpoints import (
    CONVERGENCE_WARNING_THRESHOLD,
    ResearchCheckpoint,
    is_converging,
    latest_checkpoint,
    read_checkpoints,
    recent_no_streak,
    write_checkpoint,
)
from agent.research.framework import (
    EMPTY_FRAMEWORK,
    Framework,
    FrameworkAxis,
    load_framework,
    save_framework,
)
from agent.research.ontology import (
    SOURCE_TIER,
    VERDICT,
    AssumptionMap,
    EVIDENCE_TYPE,
    EXTRACTION_METHOD,
    FrameworkAxisNote,
    GbrainEntity,
    GbrainQuerySpec,
    IngestionRun,
    MechanismCard,
    MechanismCardProposal,
    PredictionLog,
    RawSource,
    ResearchContract,
    ResearchPriority,
    ResearchThesis,
)
from agent.research.config import ResearchConfig, make_research_app
from agent.research.ingest import (
    SUPPORTED_EXTS,
    UnsupportedSourceFormat,
    extract_mechanisms,
    ingest as local_ingest,
    load_sources,
)
from agent.research.synthesis import (
    DEFAULT_JACCARD_THRESHOLD,
    FRONTIER_POSITION,
    MechanismCluster,
    SynthesisRun,
    cluster_proposals,
    list_synthesis_runs,
    read_synthesis_run,
    run_synthesis,
)
from agent.research.compress import (
    CompressedNode,
    HierarchicalCompression,
    compress_from_synthesis,
    compress_latest_synthesis,
    compress_synthesis_by_id,
    latest_compression,
    list_compressions,
    read_compression,
)
from agent.research.expression import (
    EXPRESSION_MODALITIES,
    Expression,
    list_expressions,
    read_expression,
    record_expression,
    reveal_expression,
)


__all__ = [
    "RESEARCH_CATALOG",
    "MechanismCard",
    "PredictionLog",
    "AssumptionMap",
    "ResearchThesis",
    "ResearchPriority",
    "ResearchContract",
    "EVIDENCE_TYPE",
    "EXTRACTION_METHOD",
    "VERDICT",
    "SOURCE_TIER",
    "FrameworkAxisNote",
    "RawSource",
    "MechanismCardProposal",
    "IngestionRun",
    "GbrainEntity",
    "GbrainQuerySpec",
    "ResearchConfig",
    "make_research_app",
    # Plan A — native LLM extractor
    "SUPPORTED_EXTS",
    "UnsupportedSourceFormat",
    "extract_mechanisms",
    "local_ingest",
    "load_sources",
    # Framework
    "Framework",
    "FrameworkAxis",
    "EMPTY_FRAMEWORK",
    "load_framework",
    "save_framework",
    # Layer-2 synthesis
    "MechanismCluster",
    "SynthesisRun",
    "FRONTIER_POSITION",
    "DEFAULT_JACCARD_THRESHOLD",
    "cluster_proposals",
    "run_synthesis",
    "list_synthesis_runs",
    "read_synthesis_run",
    # Layer-3 briefs
    "ProjectContext",
    "DecisionBrief",
    "QuestionForCollaborator",
    "generate_brief",
    "render_brief_markdown",
    # Checkpoints
    "ResearchCheckpoint",
    "CONVERGENCE_WARNING_THRESHOLD",
    "write_checkpoint",
    "read_checkpoints",
    "is_converging",
    "recent_no_streak",
    "latest_checkpoint",
    # Living-knowledge MVP — compression + expression
    "CompressedNode",
    "HierarchicalCompression",
    "compress_from_synthesis",
    "compress_latest_synthesis",
    "compress_synthesis_by_id",
    "list_compressions",
    "read_compression",
    "latest_compression",
    "EXPRESSION_MODALITIES",
    "Expression",
    "record_expression",
    "reveal_expression",
    "list_expressions",
    "read_expression",
]
