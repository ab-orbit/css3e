"""Deterministic layout for the on-page entity graph.

Coordinates are computed in Python and baked into static SVG, so the page needs
no graph library and makes no external request. Determinism matters: a layout
that shifts between runs would produce a diff on every rebuild of an unchanged
article.
"""

from __future__ import annotations

import pytest

from pipeline.render.graph_layout import Point, layout_graph
from pipeline.schemas.entities import Entity, EntityGraph, Mention, Relation

WIDTH, HEIGHT = 900, 520


def _entity(key, freq=3, label="Concept"):
    return Entity(
        key=key, name=key.title(), label=label, score=0.9,
        mentions=[Mention(start=i, end=i + 3, text=key[:3]) for i in range(freq)],
    )


def _graph(n=6, relations=()):
    return EntityGraph(
        entities=[_entity(f"ent{i}", freq=n - i) for i in range(n)],
        relations=[
            Relation(source_key=s, target_key=t, label=lbl, score=1.0, quote="q")
            for s, t, lbl in relations
        ],
    )


class TestGeometry:
    def test_every_entity_gets_a_node(self):
        placed = layout_graph(_graph(6), width=WIDTH, height=HEIGHT)
        assert len(placed.nodes) == 6

    def test_all_nodes_stay_inside_the_canvas(self):
        placed = layout_graph(_graph(12), width=WIDTH, height=HEIGHT)
        for node in placed.nodes:
            assert node.radius <= node.x <= WIDTH - node.radius
            assert node.radius <= node.y <= HEIGHT - node.radius

    def test_nodes_do_not_overlap(self):
        """Overlapping circles make labels unreadable."""
        placed = layout_graph(_graph(10), width=WIDTH, height=HEIGHT)
        for i, a in enumerate(placed.nodes):
            for b in placed.nodes[i + 1 :]:
                distance = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
                assert distance >= (a.radius + b.radius) * 0.9

    def test_radius_scales_with_relevance(self):
        placed = layout_graph(_graph(5), width=WIDTH, height=HEIGHT)
        by_key = {n.key: n for n in placed.nodes}
        assert by_key["ent0"].radius > by_key["ent4"].radius

    def test_layout_is_deterministic(self):
        """A shifting layout would diff every rebuild of an unchanged article."""
        first = layout_graph(_graph(8), width=WIDTH, height=HEIGHT)
        second = layout_graph(_graph(8), width=WIDTH, height=HEIGHT)
        assert [(n.key, n.x, n.y) for n in first.nodes] == [
            (n.key, n.x, n.y) for n in second.nodes
        ]


class TestLabels:
    def test_labels_do_not_overlap(self):
        """Circles were separated by radius, but a label is far wider than its
        circle — so the text collided even when the nodes did not.
        """
        graph = EntityGraph(
            entities=[
                _entity("consensus-protocol", freq=9),
                _entity("leader-follower-consensus", freq=8),
                _entity("context-aware-multi-agent-systems", freq=7),
                _entity("deep-reinforcement-learning", freq=6),
            ]
        )
        placed = layout_graph(graph, width=WIDTH, height=HEIGHT)

        for i, a in enumerate(placed.nodes):
            for b in placed.nodes[i + 1 :]:
                if abs(a.y - b.y) < 14:  # same text line
                    gap = abs(a.x - b.x)
                    assert gap >= (a.label_width + b.label_width) / 2 * 0.75, (
                        f"{a.name!r} and {b.name!r} labels overlap"
                    )

    def test_labels_stay_inside_the_canvas(self):
        placed = layout_graph(_graph(10), width=WIDTH, height=HEIGHT)
        for node in placed.nodes:
            assert node.x - node.label_width / 2 >= -1
            assert node.x + node.label_width / 2 <= WIDTH + 1

    def test_long_names_are_truncated_for_display(self):
        graph = EntityGraph(entities=[_entity("a" * 60)])
        node = layout_graph(graph, width=WIDTH, height=HEIGHT).nodes[0]
        assert len(node.display_name) <= 28
        assert node.name == ("a" * 60).title()


class TestEdges:
    def test_edges_reference_placed_nodes(self):
        placed = layout_graph(
            _graph(4, [("ent0", "ent1", "usa"), ("ent1", "ent2", "integra")]),
            width=WIDTH, height=HEIGHT,
        )
        keys = {n.key for n in placed.nodes}
        for edge in placed.edges:
            assert edge.source.key in keys
            assert edge.target.key in keys

    def test_orphaned_edges_are_not_drawn(self):
        graph = EntityGraph(
            entities=[_entity("a")],
            relations=[Relation(source_key="a", target_key="ghost", label="usa", score=1.0)],
        )
        assert layout_graph(graph, width=WIDTH, height=HEIGHT).edges == []


class TestDegenerateInput:
    def test_empty_graph_yields_nothing(self):
        placed = layout_graph(EntityGraph(), width=WIDTH, height=HEIGHT)
        assert placed.nodes == [] and placed.edges == []

    def test_single_entity_is_centred(self):
        placed = layout_graph(_graph(1), width=WIDTH, height=HEIGHT)
        assert placed.nodes[0].x == pytest.approx(WIDTH / 2, abs=1)
        assert placed.nodes[0].y == pytest.approx(HEIGHT / 2, abs=1)


class TestTypeColours:
    def test_same_label_gets_the_same_colour(self):
        graph = EntityGraph(entities=[_entity("a", label="Method"), _entity("b", label="Method")])
        placed = layout_graph(graph, width=WIDTH, height=HEIGHT)
        assert placed.nodes[0].color == placed.nodes[1].color

    def test_different_labels_differ(self):
        graph = EntityGraph(entities=[_entity("a", label="Method"), _entity("b", label="Task")])
        placed = layout_graph(graph, width=WIDTH, height=HEIGHT)
        assert placed.nodes[0].color != placed.nodes[1].color

    def test_legend_lists_each_label_once(self):
        graph = EntityGraph(
            entities=[_entity("a", label="Method"), _entity("b", label="Method"),
                      _entity("c", label="Task")]
        )
        placed = layout_graph(graph, width=WIDTH, height=HEIGHT)
        assert sorted(item.label for item in placed.legend) == ["Method", "Task"]


def test_point_is_hashable_for_use_in_sets():
    assert len({Point(1.0, 2.0), Point(1.0, 2.0)}) == 1


def test_label_width_is_not_underestimated():
    """Measured at 6.62px/char in Chromium. Estimating below that clips the
    leftmost label against the viewBox edge.
    """
    from pipeline.render.graph_layout import LABEL_CHAR_WIDTH

    assert LABEL_CHAR_WIDTH >= 6.62
