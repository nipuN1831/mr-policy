import re

from policy_wind_tunnel.civic.models import CountryPack, Problem, Representative

WORD = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    "a an the my is are was i me to of for and or in on at it this that with have has not no do does did can how what who why "
    "tell show find search about info details representative mp mla leader".split()
)

_STRIP_PARENS = re.compile(r"\s*\([^)]*\)")

# Prefixes that precede the actual name/place in natural-language queries
_NL_PREFIXES = re.compile(
    r"^\s*(?:tell\s+me\s+about|who\s+is|show\s+me|find|search|look\s+up|info\s+(?:on|about)|"
    r"details?\s+(?:on|about|of)|about|mp\s+(?:for|from|of)|representative\s+(?:for|from|of)|"
    r"my\s+(?:mp|representative|mla|leader)|representative\s+in|mp\s+in)\s+",
    re.IGNORECASE,
)


def _words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP_WORDS and len(w) > 1}


def _score(problem: Problem, words: set[str]) -> int:
    keyword_words = set().union(*(_words(k) for k in problem.keywords))
    title_words = _words(problem.title)
    return 2 * len(words & keyword_words) + len(words & title_words)


def find_problems(pack: CountryPack, text: str, limit: int = 3) -> list[Problem]:
    words = _words(text)
    if not words:
        return []
    scored = [(_score(problem, words), problem) for problem in pack.problems]
    ranked = sorted((item for item in scored if item[0] > 0), key=lambda item: -item[0])
    return [problem for _, problem in ranked[:limit]]


def _normalise(text: str) -> str:
    return _STRIP_PARENS.sub("", text).strip().lower()


def find_representatives(pack: CountryPack, constituency: str) -> list[Representative]:
    cleaned = _NL_PREFIXES.sub("", constituency).strip()
    wanted = _normalise(cleaned)
    if not wanted:
        return []
    # exact constituency match
    exact = [r for r in pack.representatives if _normalise(r.constituency) == wanted]
    if exact:
        return exact
    # exact name match
    exact_name = [r for r in pack.representatives if _normalise(r.name) == wanted]
    if exact_name:
        return exact_name
    # partial name match (all query words appear in name)
    wanted_words = _words(wanted)
    if not wanted_words:
        return []
    name_fuzzy = [r for r in pack.representatives if wanted_words.issubset(_words(_normalise(r.name)))]
    if name_fuzzy:
        return name_fuzzy
    # fuzzy constituency match (all query words appear in constituency)
    fuzzy = [r for r in pack.representatives if wanted_words.issubset(_words(_normalise(r.constituency)))]
    return fuzzy
