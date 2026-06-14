"""design_data_model — derive entities/fields from the PRD's features and personas.

Deterministic: always seed a User entity (from personas), then mint one entity per
feature's salient noun, each with sensible default fields (id, timestamps, a couple of
domain fields). Returns {entities: {Name: {fields: {field: type}}}}. No LLM, no network.
"""
from __future__ import annotations


from pydantic import BaseModel, Field

from aps.tools.base import BaseTool
from aps.state.models import ToolResult, Feature, Persona
from aps.tools.analysis._text import tokenize
from aps.tools.analysis._inflect import singularize

# Tokens that must never become a database entity. Feature titles are often raw pain/issue
# text ("Solve: this is a great app...", "Inconvenient, annoying..."), so the leading token
# is frequently a VERB or ADJECTIVE, not a domain noun. We filter those out and take the
# first remaining noun-like token; if none survives we return None and the caller pads with a
# generic entity rather than minting a verb/adjective entity (e.g. `Rejects`, `Great`).
_STOP_ENTITY = {
    # tech-category words that tokenize from ideas like "AI SaaS for X" — never domain entities
    "saas", "paas", "iaas", "startup", "venture", "mvp", "platform",
    # filler / framing
    "solve", "feature", "request", "core", "table", "stakes", "with", "that", "from",
    "this", "your", "their", "into", "more", "than", "when", "what", "which", "where",
    # continuation / subordinating conjunctions that lead an orphaned clause fragment — these
    # mint junk entities (the "/howevers" bug). Same set as _text._CLAUSE_SKIP_LEAD.
    "however", "therefore", "moreover", "furthermore", "meanwhile", "nevertheless", "thus",
    "hence", "otherwise", "besides", "although", "though", "whereas", "instead", "anyway",
    "while", "since", "because", "unless", "after", "before",
    "please", "describe", "description", "related", "problem", "also", "currently", "just",
    "plain", "thing", "things", "stuff", "able", "unable", "need", "needs", "want", "wants",
    # verbs (pain/feature phrasing)
    "reject", "rejects", "rejected", "screen", "screens", "build", "builds", "create",
    "creates", "manage", "manages", "track", "tracks", "enable", "enables", "improve",
    "improves", "optimize", "optimizes", "generate", "generates", "provide", "provides",
    "handle", "handles", "reduce", "reduces", "automate", "automates", "integrate",
    "integrates", "detect", "detects", "analyze", "analyzes", "find", "finds", "make",
    "makes", "allow", "allows", "ensure", "ensures", "deliver", "delivers", "support",
    "supports", "update", "updates", "share", "shares", "store", "stores", "save", "saves",
    "help", "helps", "keep", "keeps", "show", "shows", "view", "views", "send", "sends",
    "resolve", "resolves", "fix", "fixes", "edit", "edits", "remove", "removes", "delete",
    "deletes", "cancel", "cancels", "submit", "submits", "solved", "solving",
    # adjectives / adverbs (the common leakers)
    "great", "awesome", "amazing", "awful", "terrible", "good", "best", "better", "worse",
    "worst", "easy", "simple", "hard", "difficult", "fast", "slow", "quick", "modern",
    "legacy", "secure", "private", "public", "smart", "automatic", "automated", "manual",
    "seamless", "intuitive", "powerful", "flexible", "scalable", "reliable", "robust",
    "custom", "free", "premium", "basic", "advanced", "real", "live", "instant",
    "convenient", "inconvenient", "frustrating", "annoying", "bothersome", "broken",
    "missing", "limited", "lacking", "native", "mobile", "online", "offline", "local",
    "cloud", "open", "full", "partial", "high", "many", "some", "very", "really", "super",
    "extremely", "qualified", "valid", "existing", "poor", "time",
    # issue-template / feature-phrase / plumbing fragments that leak as entities
    "descr", "scheduled", "schedule", "external", "internal", "tool", "tools",
    "integration", "integrations", "auto", "additional", "context", "current",
    "solution", "solutions", "alternative", "alternatives", "behaviour", "behavior",
    "enhancement", "reproduce", "steps", "expected", "actual", "export", "import",
    # time / narrative words that leak from conversational forum snippets
    "year", "years", "month", "months", "week", "weeks", "day", "days", "hour", "hours",
    "ago", "response", "responses", "today", "yesterday", "tomorrow",
    # common ADJECTIVES that modify the real head noun ("personal FINANCE", "social MEDIA",
    # "multiplayer CHESS") — they tokenize first but are never the domain entity.
    "personal", "multiplayer", "singleplayer", "social", "realtime", "distributed",
    "centralized", "decentralized", "weird", "damn", "freaking", "darn", "nice", "cool",
    "neat", "fancy", "handy", "tiny", "huge", "massive", "dumb", "clever", "sleek", "minimal",
    "minimalist", "lightweight", "everyday", "comprehensive", "complete", "entire", "whole",
    "various", "multiple", "several", "general", "specific", "particular", "main", "primary",
    "secondary", "essential", "critical", "important", "central", "global", "national",
    "international", "regional", "digital", "virtual", "physical", "remote", "automated",
    "integrated", "dedicated", "enhanced", "improved",
    # pure-verb GERUNDS that are never a domain entity (unlike nominal -ing words such as
    # planning/screening/ranking/tracking/voting, which we keep). Their base verbs are already
    # denied above; listing the -ing forms avoids a blanket -ing rule that would drop the good ones.
    "managing", "building", "making", "getting", "using", "handling", "running", "doing",
    "trying", "looking", "working", "helping", "keeping", "putting", "taking", "giving",
    "creating", "providing", "ensuring", "allowing", "enabling", "improving", "reducing",
    "increasing", "automating", "integrating", "generating", "delivering", "supporting",
}
# -ly words that are genuinely NOUNS — exempt from the adverb rule below.
_LY_NOUNS = {"family", "supply", "assembly", "anomaly", "ally", "rally", "tally", "bully",
             "belly", "jelly", "monopoly", "duopoly", "reply", "panoply", "homily"}


def _is_modifier(t: str) -> bool:
    """Morphological adjective/adverb test for the long tail the denylist can't enumerate:
    -ly adverbs ('quickly', 'daily') and -ized/-ised participles ('decentralized', 'optimized')
    are never domain entities. High-precision (a tiny -ly noun allowlist guards 'family' etc.)."""
    if t.endswith("ly") and t not in _LY_NOUNS:
        return True
    if t.endswith(("ized", "ised", "izing", "ising")):
        return True
    return False


def _candidate_nouns(text: str) -> list[str]:
    """Clean, noun-like tokens from free text: alpha-only (drops hyphenated fragments like
    'privacy-first' / 'non-cons'), length >= 4, not a known verb/adjective/filler, and not a
    morphological adverb/participle."""
    return [t for t in tokenize(text or "")
            if len(t) >= 4 and t.isalpha() and t not in _STOP_ENTITY and not _is_modifier(t)]


class Args(BaseModel):
    features: list[Feature] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)
    idea: str = Field("", description="product idea — the primary source of clean domain nouns")
    max_entities: int = Field(8, ge=1, le=20)


class DesignDataModel(BaseTool):
    name = "design_data_model"
    namespace = "architecture"
    description = (
        "Design the data model (entities and fields) from the product idea, PRD features and "
        "personas. Seeds a User entity, then mints entities from clean DOMAIN NOUNS (the idea "
        "first — feature titles are often raw pain text). Use first in TRD assembly — the API "
        "contract is generated from this."
    )
    args_schema = Args

    def _run(self, args: Args) -> ToolResult:
        entities: dict[str, dict] = {
            "User": {"fields": {"id": "uuid", "email": "string", "role": "string",
                                 "created_at": "datetime"}}
        }
        seen = {"user"}

        def _add(text: str) -> None:
            for noun in _candidate_nouns(text):
                name = singularize(noun).capitalize()
                if len(name) < 4 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                entities[name] = {"fields": {
                    "id": "uuid", "owner_id": "uuid", "name": "string",
                    "status": "string", "created_at": "datetime", "updated_at": "datetime",
                }}
                if len(entities) >= args.max_entities:
                    return

        # The IDEA is the clean domain-noun source (e.g. "habit tracker for couples" ->
        # Habit, Tracker, Couple). Feature titles / persona goals are noisier (forum prose),
        # so we only fall back to mining them when the idea alone is too thin (< 4 entities).
        # This keeps adjectives/verbs from clean-but-prosey feature labels (Right, Numeric,
        # Locked, Lose) out of the data model.
        _add(args.idea)
        if len(entities) < 4:
            for f in args.features:
                _add(f.title)
                if len(entities) >= 4 or len(entities) >= args.max_entities:
                    break
        if len(entities) < 4:
            for p in args.personas:
                for g in (p.goals or []):
                    _add(g)
                if len(entities) >= 4 or len(entities) >= args.max_entities:
                    break
        # Guarantee a non-trivial model even when nothing clean was found, rather than
        # minting a verb/adjective/fragment entity to pad the count.
        if len(entities) < 2:
            entities["Record"] = {"fields": {
                "id": "uuid", "owner_id": "uuid", "title": "string",
                "created_at": "datetime", "updated_at": "datetime",
            }}
        return ToolResult(ok=True, payload={"entities": entities})


TOOL = DesignDataModel()

if __name__ == "__main__":
    import json
    out = TOOL.run(features=[Feature(title="Resume parsing engine", description="x", priority="Must").model_dump()])
    print(json.dumps(out.model_dump(), indent=2, default=str))
