"""Deterministic layout for the on-page entity graph.

Coordinates are computed here and baked into static SVG, so the published page
carries no graph library and makes no external request — the same constraint
the rest of this site holds itself to.

Determinism is a requirement, not a nicety: a force simulation seeded by
`random` would move every node on each rebuild, producing a diff for an article
whose content never changed. The layout is therefore a closed-form radial
placement, plus a fixed number of repulsion passes with no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pipeline.schemas.entities import EntityGraph

# Ordered so the most common label in a CS paper takes the first, strongest
# colour. Same palette family as the article's category accents.
LABEL_COLORS = {
    "Concept": "#2E7D5B",
    "Method": "#8A5A00",
    "System": "#E8172D",
    "Task": "#2B5F86",
    "Dataset": "#6B3FA0",
    "Metric": "#B4233D",
    "Software": "#0F6C6C",
    "Organization": "#7A4B2A",
}
FALLBACK_COLOR = "#5A5A5A"

MIN_RADIUS = 16.0
MAX_RADIUS = 40.0
REPULSION_PASSES = 60


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class Node:
    key: str
    name: str
    label: str
    x: float
    y: float
    radius: float
    color: str
    frequency: int


@dataclass
class Edge:
    source: Node
    target: Node
    label: str
    quote: str


@dataclass
class LegendItem:
    label: str
    color: str


@dataclass
class PlacedGraph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    legend: list[LegendItem] = field(default_factory=list)
    width: int = 900
    height: int = 520


def color_for(label: str) -> str:
    return LABEL_COLORS.get(label, FALLBACK_COLOR)


def layout_graph(graph: EntityGraph, *, width: int = 900, height: int = 520) -> PlacedGraph:
    """Place entities on a canvas, most relevant at the centre."""
    entities = sorted(graph.entities, key=lambda e: (-e.relevance, e.key))
    if not entities:
        return PlacedGraph(width=width, height=height)

    nodes = _place(entities, width, height)
    by_key = {n.key: n for n in nodes}

    edges = [
        Edge(
            source=by_key[r.source_key],
            target=by_key[r.target_key],
            label=r.label,
            quote=r.quote,
        )
        for r in graph.connected_relations()
        if r.source_key in by_key and r.target_key in by_key
    ]

    seen: dict[str, str] = {}
    for node in nodes:
        seen.setdefault(node.label, node.color)
    legend = [LegendItem(label=lbl, color=col) for lbl, col in sorted(seen.items())]

    return PlacedGraph(nodes=nodes, edges=edges, legend=legend, width=width, height=height)


def _place(entities, width: int, height: int) -> list[Node]:
    """Radial placement: highest relevance at the centre, rest on rings."""
    max_relevance = max(e.relevance for e in entities) or 1.0
    centre = Point(width / 2, height / 2)

    nodes: list[Node] = []
    for index, entity in enumerate(entities):
        scale = entity.relevance / max_relevance
        radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * scale

        if index == 0:
            x, y = centre.x, centre.y
        else:
            # Ring 1 holds 6 nodes, ring 2 holds 12, and so on: a spiral would
            # crowd the centre, and a grid would say nothing about relevance.
            ring, position, ring_size = _ring_for(index)
            # The golden angle offset keeps successive rings from lining their
            # nodes up radially, which reads as spokes rather than a graph.
            angle = (2 * math.pi * position / ring_size) + ring * 0.618
            spread_x = (width / 2 - MAX_RADIUS - 10) * ring / _max_ring(len(entities))
            spread_y = (height / 2 - MAX_RADIUS - 10) * ring / _max_ring(len(entities))
            x = centre.x + math.cos(angle) * spread_x
            y = centre.y + math.sin(angle) * spread_y

        nodes.append(
            Node(
                key=entity.key,
                name=entity.name,
                label=entity.label,
                x=x,
                y=y,
                radius=radius,
                color=color_for(entity.label),
                frequency=entity.frequency,
            )
        )

    _relax(nodes, width, height)
    return nodes


def _ring_for(index: int) -> tuple[int, int, int]:
    """Ring number, position within it, and its capacity, for node `index`."""
    ring = 1
    consumed = 1
    while True:
        capacity = 6 * ring
        if index < consumed + capacity:
            return ring, index - consumed, capacity
        consumed += capacity
        ring += 1


def _max_ring(count: int) -> int:
    ring, consumed = 1, 1
    while consumed + 6 * ring < count:
        consumed += 6 * ring
        ring += 1
    return ring


def _relax(nodes: list[Node], width: int, height: int) -> None:
    """Push overlapping nodes apart, then clamp inside the canvas.

    A fixed pass count with no randomness keeps the result reproducible.
    """
    for _ in range(REPULSION_PASSES):
        moved = False
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                dx, dy = b.x - a.x, b.y - a.y
                distance = math.hypot(dx, dy)
                minimum = a.radius + b.radius + 6

                if distance >= minimum:
                    continue
                moved = True
                if distance < 1e-6:
                    # Exactly coincident: separate along a fixed axis rather
                    # than a random one, to stay deterministic.
                    dx, dy, distance = 1.0, 0.0, 1.0
                push = (minimum - distance) / 2
                ux, uy = dx / distance, dy / distance
                a.x -= ux * push
                a.y -= uy * push
                b.x += ux * push
                b.y += uy * push

        for node in nodes:
            node.x = min(max(node.x, node.radius), width - node.radius)
            node.y = min(max(node.y, node.radius), height - node.radius)

        if not moved:
            break
