# GATEWAY layer for practice mode: validates the exercise parameters and translates failures into ValueError.
from functions.practice import KINDS, check, new_exercise


class PracticeGateway:

    @staticmethod
    def _params(kind, seed, difficulty):
        if kind not in KINDS:
            raise ValueError(f"Unknown kind {kind!r}. Available: {', '.join(KINDS)}.")
        try:
            seed, difficulty = int(seed), int(difficulty)
        except (TypeError, ValueError):
            raise ValueError("'seed' and 'difficulty' must be integers.")
        if not 0 <= seed <= 10 ** 9 or difficulty not in (1, 2, 3):
            raise ValueError("'seed' must be between 0 and 1000000000 and 'difficulty' must be 1, 2 or 3.")
        return kind, seed, difficulty

    def kinds(self):
        return [{"kind": k, "title": t} for k, t in KINDS.items()]

    def new(self, kind, seed, difficulty):
        return new_exercise(*self._params(kind, seed, difficulty))

    def check(self, kind, seed, difficulty, answer):
        if not isinstance(answer, dict):
            raise ValueError("Field 'answer' must be an object.")
        try:
            return check(*self._params(kind, seed, difficulty), answer)
        except ValueError:
            raise
        except (TypeError, AttributeError, KeyError) as e:
            raise ValueError(f"Malformed answer: {e}")
