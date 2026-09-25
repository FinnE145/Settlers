"""A few random games end to end (more with: python -m tests.simulate 100)."""

import pytest

from .simulate import play_random_game


@pytest.mark.parametrize("seed", range(3))
def test_random_game_runs_clean(seed):
    result = play_random_game(seed, max_actions=2500)
    assert result["actions"] > 100
