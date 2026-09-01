"""Progress weighting for the authoring console.

Weights are measured wall-clock shares, not node counts. On a real run of
121k characters the graph took 1300s, of which the media branch (2 nodes of 22)
took ~1130s. Weighting by node count would put the bar at 90% three minutes in
and freeze it there for twenty — a bar that lies about what is left.

Measured, from `articles/.../context-aware-mas`:

    ingest_pdf        1.8s
    analyze_paper    58.7s
    infer_theme       0.8s
    fan-out (9)     108.0s
    generate_audio  462.8s
    generate_slides 666.7s
    assemble/render/publish  <1s
"""

from __future__ import annotations

FANOUT_NODES = (
    "gen_hero",
    "gen_categories",
    "gen_mindmap",
    "gen_tables",
    "gen_essay_condensed",
    "gen_essay_full",
    "gen_workshop",
    "gen_seo",
    "gen_downloads",
    "gen_entities",
)

# Phase -> the nodes that constitute it, in execution order.
PHASE_NODES: dict[str, tuple[str, ...]] = {
    "Extração": ("ingest_pdf",),
    "Análise": ("analyze_paper", "review_extraction", "infer_theme"),
    "Conteúdo": FANOUT_NODES,
    "Mídia": ("generate_audio", "generate_slides"),
    "Publicação": ("assemble", "render_html", "publish"),
}

# Shares of measured wall-clock, rounded and normalized to 1.0.
PHASE_WEIGHTS: dict[str, float] = {
    "Extração": 0.002,
    "Análise": 0.046,
    "Conteúdo": 0.083,
    "Mídia": 0.868,
    "Publicação": 0.001,
}

_NODE_TO_PHASE = {
    node: phase for phase, nodes in PHASE_NODES.items() for node in nodes
}


def phase_for_node(node: str) -> str | None:
    """The phase a node belongs to, or None when it is not tracked."""
    return _NODE_TO_PHASE.get(node)


class RunProgress:
    """Tracks which nodes have completed and derives weighted percentages."""

    def __init__(self) -> None:
        self._done: set[str] = set()

    def all_nodes(self) -> list[str]:
        return [node for nodes in PHASE_NODES.values() for node in nodes]

    def complete(self, node: str) -> None:
        """Mark a node done. Idempotent: `publish` fires twice per run, and a
        bar that could exceed 100% would be worse than one that stalls.
        """
        if node in _NODE_TO_PHASE:
            self._done.add(node)

    def phase_pct(self, phase: str) -> int:
        nodes = PHASE_NODES[phase]
        done = sum(1 for node in nodes if node in self._done)
        return round(100 * done / len(nodes))

    @property
    def total_pct(self) -> int:
        total = sum(
            PHASE_WEIGHTS[phase] * self.phase_pct(phase) for phase in PHASE_NODES
        )
        rounded = min(100, round(total))

        # Publicação weighs 0.001, so rounding alone reports 100% while that
        # phase has not started. Hold at 99 until every phase is actually done:
        # a bar that says "done" with work pending is worse than a slow one.
        if rounded == 100 and any(
            self.phase_pct(phase) < 100 for phase in PHASE_NODES
        ):
            return 99
        return rounded

    def phases(self) -> list[dict]:
        """Per-phase state for the console, in execution order."""
        result = []
        first_unfinished_seen = False

        for phase in PHASE_NODES:
            pct = self.phase_pct(phase)
            done = pct == 100
            active = not done and not first_unfinished_seen
            if not done:
                first_unfinished_seen = True
            result.append(
                {"name": phase, "pct": pct, "done": done, "active": active}
            )
        return result

    def snapshot(self) -> dict:
        return {"total_pct": self.total_pct, "phases": self.phases()}
