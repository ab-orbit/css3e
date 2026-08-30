"""Entity extraction with GLiNER.

Relations are NOT extracted here. GLiREL was measured on this corpus and
produced unusable output: at window level the top score was 0.031 with both
directions of a pair tied, and even at sentence level (10x better, 0.363) the
correct direction lost to its inverse by a 0.05 margin. It knows THAT two
entities are related, not in which direction — so relations come from
pipeline.extraction.relations instead, where an LLM infers them over these
entities and every one must cite a sentence verified against the source.

GLiNER is a zero-shot span model: the label set is supplied at call time, so a
new entity type costs a config edit rather than a fine-tune. It returns
character spans, which is why it was chosen over asking an LLM for a list of
concepts — every entity rendered on the published page can be traced to the
passage it was found in.

Models load from HF_HOME (pointed at the external volume, see Settings), run on
MPS when available, and are cached per process: loading is measured in seconds
and a pipeline run extracts once.

Everything here is fail-soft. Missing torch, a missing model, or an unmounted
volume yields an empty EntityGraph and a warning — never a failed build. The
graph node treats entities the same way it treats audio and slides.
"""

from __future__ import annotations

import functools
import logging
import os
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from pipeline.config import Settings
from pipeline.extraction.chunking import Chunk, chunk_text, remap_offset
from pipeline.schemas.entities import Entity, EntityGraph, Mention, Relation

logger = logging.getLogger(__name__)


class EntityExtractionError(RuntimeError):
    pass


# Label sets are zero-shot: these are prompts, not trained classes. Tuned for
# computer-science papers, which is what this site publishes.
DEFAULT_ENTITY_LABELS = [
    "Method",
    "Task",
    "System",
    "Concept",
    "Dataset",
    "Metric",
    "Software",
    "Organization",
]

DEFAULT_RELATION_LABELS = [
    "is part of",
    "uses",
    "extends",
    "evaluates",
    "compares to",
    "applies to",
    "proposed by",
    "enables",
]


def _normalize_key(surface: str) -> str:
    """Fold a surface form into a deduplication key.

    "Multi-Agent Systems", "multi agent systems" and "Multi-Agent  Systems"
    are one entity. Acronyms stay distinct from their expansion — merging
    "MAS" into "Multi-Agent Systems" needs coreference, which these models do
    not do, and guessing would silently fuse unrelated entities.
    """
    lowered = surface.lower().strip()
    collapsed = re.sub(r"[\s\-_]+", " ", lowered)
    return re.sub(r"[^a-z0-9 ]", "", collapsed).strip()


def _hf_home(settings: Settings) -> str:
    return str(Path(settings.entity_model_dir).expanduser())


@lru_cache(maxsize=2)
def _load_gliner(model_id: str, hf_home: str, device: str):
    os.environ["HF_HOME"] = hf_home
    try:
        from gliner import GLiNER
    except ImportError as exc:
        raise EntityExtractionError(
            "gliner is not installed. `uv pip install -e \".[entities]\"` to enable "
            "entity extraction, or leave ENTITY_EXTRACTION=false."
        ) from exc

    try:
        return GLiNER.from_pretrained(model_id).to(device).eval()
    except Exception as exc:  # noqa: BLE001 - any load failure is fail-soft
        raise EntityExtractionError(f"could not load GLiNER {model_id!r}: {exc}") from exc


def _patch_glirel_hub_compat(GLiREL) -> None:
    """Bridge glirel 1.2.1 to huggingface_hub 1.x.

    glirel declares ``_from_pretrained(*, proxies, resume_download, ...)`` as
    required keyword-only arguments. huggingface_hub dropped both in its 1.x
    line, so ``from_pretrained`` no longer supplies them and every load dies
    with "missing 2 required keyword-only arguments". Passing them at the call
    site does not help — hub 1.x does not forward unknown kwargs down.

    This supplies defaults for exactly those two parameters and changes nothing
    else. It is a shim against a specific broken interaction between two
    pinned versions, not a general wrapper: when glirel updates its signature,
    delete it. (The same release also omits `loguru` from its dependencies, so
    treat its packaging as unreliable.)
    """
    if getattr(GLiREL._from_pretrained, "_css3e_patched", False):
        return

    original = GLiREL._from_pretrained.__func__

    @classmethod
    @functools.wraps(original)
    def _shim(cls, *args, proxies=None, resume_download=False, **kwargs):
        return original(
            cls, *args, proxies=proxies, resume_download=resume_download, **kwargs
        )

    _shim.__func__._css3e_patched = True
    GLiREL._from_pretrained = _shim


@lru_cache(maxsize=2)
def _load_glirel(model_id: str, hf_home: str, device: str):
    os.environ["HF_HOME"] = hf_home
    try:
        from glirel import GLiREL
    except ImportError as exc:
        raise EntityExtractionError("glirel is not installed") from exc

    _patch_glirel_hub_compat(GLiREL)

    try:
        return GLiREL.from_pretrained(model_id).to(device).eval()
    except Exception as exc:  # noqa: BLE001
        raise EntityExtractionError(f"could not load GLiREL {model_id!r}: {exc}") from exc


def resolve_device(preferred: str = "auto") -> str:
    """Pick the compute device, degrading to CPU rather than failing."""
    if preferred != "auto":
        return preferred
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def extract_entities(
    text: str,
    *,
    settings: Settings,
    entity_labels: list[str] | None = None,
    relation_labels: list[str] | None = None,
) -> EntityGraph:
    """Run GLiNER over windowed `text`, then GLiREL over co-occurring pairs.

    Raises EntityExtractionError on any model/dependency problem; the caller
    (the graph node) turns that into an empty graph plus a warning.
    """
    if not text.strip():
        return EntityGraph()

    entity_labels = entity_labels or DEFAULT_ENTITY_LABELS
    relation_labels = relation_labels or DEFAULT_RELATION_LABELS
    device = resolve_device(settings.entity_device)
    hf_home = _hf_home(settings)

    gliner = _load_gliner(settings.gliner_model, hf_home, device)
    chunks = chunk_text(
        text, max_chars=settings.entity_chunk_chars, overlap=settings.entity_chunk_overlap
    )
    logger.info(
        "Extracting entities from %s chars in %s windows on %s",
        f"{len(text):,}",
        len(chunks),
        device,
    )

    entities = _scan_entities(gliner, chunks, entity_labels, settings)
    return EntityGraph(entities=entities, engine=f"gliner={settings.gliner_model}")


def _scan_entities(
    gliner, chunks: list[Chunk], labels: list[str], settings: Settings
) -> list[Entity]:
    """Predict per window, remap offsets, then merge by normalized key."""
    by_key: dict[str, list[tuple[Mention, str, float]]] = defaultdict(list)

    for chunk in chunks:
        try:
            found = gliner.predict_entities(
                chunk.text, labels, threshold=settings.entity_threshold
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("GLiNER failed on window at %s: %s", chunk.start, exc)
            continue

        for item in found:
            key = _normalize_key(item["text"])
            if not key:
                continue
            mention = Mention(
                start=remap_offset(chunk, item["start"]),
                end=remap_offset(chunk, item["end"]),
                text=item["text"],
            )
            by_key[key].append((mention, item["label"], float(item["score"])))

    return _merge(by_key, settings)


def _merge(
    by_key: dict[str, list[tuple[Mention, str, float]]], settings: Settings
) -> list[Entity]:
    """Collapse mentions into entities, dropping overlap-induced duplicates."""
    entities: list[Entity] = []

    for key, hits in by_key.items():
        # Overlapping windows see the same occurrence twice; the offset makes
        # the duplicate exact, so dedup on it.
        unique: dict[int, Mention] = {}
        labels: defaultdict[str, float] = defaultdict(float)
        scores: list[float] = []

        for mention, label, score in hits:
            unique.setdefault(mention.start, mention)
            labels[label] += score
            scores.append(score)

        surfaces: defaultdict[str, int] = defaultdict(int)
        for mention in unique.values():
            surfaces[mention.text] += 1

        entities.append(
            Entity(
                key=key,
                # Most frequent surface form, so the page shows "Multi-Agent
                # Systems" rather than whichever variant happened to be first.
                name=max(surfaces.items(), key=lambda kv: kv[1])[0],
                label=max(labels.items(), key=lambda kv: kv[1])[0],
                score=sum(scores) / len(scores),
                mentions=sorted(unique.values(), key=lambda m: m.start),
            )
        )

    entities.sort(key=lambda e: e.relevance, reverse=True)
    return entities[: settings.entity_max_count]


def _scan_relations(
    chunks: list[Chunk],
    graph: EntityGraph,
    labels: list[str],
    settings: Settings,
    device: str,
    hf_home: str,
) -> list[Relation]:
    """Ask GLiREL about entity pairs that co-occur inside one window.

    Only same-window pairs are considered: a relation between entities that
    never appear together has no passage to cite, and citing nothing is the
    thing this design exists to avoid.
    """
    glirel = _load_glirel(settings.glirel_model, hf_home, device)
    kept = {e.key: e for e in graph.entities}
    seen: set[tuple[str, str, str]] = set()
    relations: list[Relation] = []

    for chunk in chunks:
        local = _entities_in_window(kept, chunk)
        if len(local) < 2:
            continue

        tokens = chunk.text.split()
        spans = _token_spans(chunk, local, tokens)
        if len(spans) < 2:
            continue

        try:
            predicted = glirel.predict_relations(
                tokens, labels, threshold=settings.relation_threshold, ner=spans
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("GLiREL failed on window at %s: %s", chunk.start, exc)
            continue

        for item in predicted:
            source = _normalize_key(" ".join(item["head_text"]))
            target = _normalize_key(" ".join(item["tail_text"]))
            if source not in kept or target not in kept or source == target:
                continue

            signature = (source, target, item["label"])
            if signature in seen:
                continue
            seen.add(signature)

            relations.append(
                Relation(
                    source_key=source,
                    target_key=target,
                    label=item["label"],
                    score=float(item["score"]),
                    quote=chunk.text.strip()[: settings.relation_quote_chars],
                    quote_start=chunk.start,
                )
            )

    relations.sort(key=lambda r: r.score, reverse=True)
    return relations[: settings.relation_max_count]


def _entities_in_window(kept: dict[str, Entity], chunk: Chunk) -> dict[str, Mention]:
    """Entities with at least one mention inside this window."""
    local: dict[str, Mention] = {}
    for key, entity in kept.items():
        for mention in entity.mentions:
            if chunk.start <= mention.start and mention.end <= chunk.end:
                local.setdefault(key, mention)
                break
    return local


def _token_spans(
    chunk: Chunk, local: dict[str, Mention], tokens: list[str]
) -> list[list]:
    """Convert character mentions into the token-index spans GLiREL expects.

    GLiREL is token-indexed while GLiNER is character-indexed, so the two must
    be reconciled here. A mention whose characters do not line up with token
    boundaries is dropped rather than approximated — a misaligned span would
    attach a relation to the wrong words.
    """
    starts: list[int] = []
    cursor = 0
    for token in tokens:
        index = chunk.text.find(token, cursor)
        starts.append(index)
        cursor = index + len(token)

    spans: list[list] = []
    for key, mention in local.items():
        local_start = mention.start - chunk.start
        local_end = mention.end - chunk.start
        try:
            first = starts.index(local_start)
        except ValueError:
            continue
        last = first
        while last + 1 < len(tokens) and starts[last + 1] < local_end:
            last += 1
        spans.append([first, last, key, mention.text])

    return spans
