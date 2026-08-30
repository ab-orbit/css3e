"""Progress weighting for the authoring console.

Weights come from measured wall-clock, not node count. On a real 1300s run the
media branch took ~1130s — 87% of the time in 2 of 22 nodes. Weighting by node
count would put the bar at 90% after three minutes and freeze it there for
twenty, which is a bar that lies.
"""

from __future__ import annotations

import pytest

from pipeline.server.progress import (
    FANOUT_NODES,
    PHASE_WEIGHTS,
    RunProgress,
    phase_for_node,
)


class TestNodeMapping:
    @pytest.mark.parametrize(
        "node,phase",
        [
            ("ingest_pdf", "Extração"),
            ("analyze_paper", "Análise"),
            ("infer_theme", "Análise"),
            ("gen_hero", "Conteúdo"),
            ("gen_entities", "Conteúdo"),
            ("generate_audio", "Mídia"),
            ("generate_slides", "Mídia"),
            ("assemble", "Publicação"),
            ("render_html", "Publicação"),
            ("publish", "Publicação"),
        ],
    )
    def test_each_node_maps_to_its_phase(self, node, phase):
        assert phase_for_node(node) == phase

    def test_unknown_node_maps_to_nothing(self):
        assert phase_for_node("gen_futuro") is None

    def test_every_fanout_node_is_accounted_for(self):
        """A node missing from the map would silently never advance the bar."""
        assert all(phase_for_node(n) == "Conteúdo" for n in FANOUT_NODES)


class TestWeights:
    def test_weights_sum_to_one(self):
        assert sum(PHASE_WEIGHTS.values()) == pytest.approx(1.0)

    def test_media_dominates_the_weighting(self):
        """It is 87% of measured wall-clock; the bar must reflect that."""
        assert PHASE_WEIGHTS["Mídia"] > 0.7
        assert PHASE_WEIGHTS["Mídia"] > sum(
            w for p, w in PHASE_WEIGHTS.items() if p != "Mídia"
        )


class TestRunProgress:
    def test_starts_at_zero(self):
        assert RunProgress().total_pct == 0

    def test_completing_the_content_phase_does_not_pass_the_media_weight(self):
        """The failure mode this exists to prevent: 90% after three minutes."""
        progress = RunProgress()
        for node in ["ingest_pdf", "analyze_paper", "infer_theme", *FANOUT_NODES]:
            progress.complete(node)

        assert progress.total_pct < 25

    def test_a_partially_done_phase_reports_partial_credit(self):
        progress = RunProgress()
        progress.complete("gen_hero")
        content = next(p for p in progress.phases() if p["name"] == "Conteúdo")

        assert 0 < content["pct"] < 100

    def test_never_reports_one_hundred_while_work_remains(self):
        """Publicação weighs 0.001, so 99.9% rounds to 100 while the phase has
        not started. A bar that says "done" with work pending is a lie.
        """
        progress = RunProgress()
        for node in progress.all_nodes():
            if phase_for_node(node) != "Publicação":
                progress.complete(node)

        assert progress.total_pct == 99

    def test_finishing_everything_reaches_one_hundred(self):
        progress = RunProgress()
        for node in progress.all_nodes():
            progress.complete(node)

        assert progress.total_pct == 100

    def test_duplicate_completion_is_idempotent(self):
        """publish runs twice per graph execution; the bar must not exceed 100."""
        progress = RunProgress()
        for node in progress.all_nodes():
            progress.complete(node)
            progress.complete(node)

        assert progress.total_pct == 100

    def test_unknown_node_does_not_move_the_bar(self):
        progress = RunProgress()
        progress.complete("gen_inexistente")
        assert progress.total_pct == 0

    def test_phases_report_active_and_done_state(self):
        progress = RunProgress()
        progress.complete("ingest_pdf")
        by_name = {p["name"]: p for p in progress.phases()}

        assert by_name["Extração"]["done"] is True
        assert by_name["Mídia"]["done"] is False

    def test_phase_order_follows_execution(self):
        names = [p["name"] for p in RunProgress().phases()]
        assert names == ["Extração", "Análise", "Conteúdo", "Mídia", "Publicação"]
