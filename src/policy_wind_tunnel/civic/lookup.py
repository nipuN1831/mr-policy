import re

from policy_wind_tunnel.civic.models import CountryPack, Problem, Representative

WORD = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    "a an the my is are was i me to of for and or in on at it this that with have has not no do does did can how what who why".split()
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


def find_representatives(pack: CountryPack, constituency: str) -> list[Representative]:
    wanted = constituency.strip().lower()
    return [r for r in pack.representatives if wanted and r.constituency.lower() == wanted]
