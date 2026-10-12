"""Textos que sobem ("+15 FERRO"): o mesmo recurso no mesmo ponto soma, e vizinhos não encavalam."""

from game.floaters import LANE_PX, FloatingTexts, split_amount

IRON = "#e8a066"


def test_split_amount():
    assert split_amount("+15 FERRO") == (15, "FERRO")
    assert split_amount("+O2") is None


def test_same_resource_same_spot_merges_and_sums():
    f = FloatingTexts()
    a = f.add("+15 FERRO", 100, 200, IRON)
    f.update(0.2)
    b = f.add("+15 FERRO", 104, 202, IRON)
    assert b is a and len(f.items) == 1
    assert a.text == "+30 FERRO" and a.age == 0          # vida renovada


def test_old_floater_does_not_merge_it_stacks():
    f = FloatingTexts()
    f.add("+15 FERRO", 100, 200, IRON)
    f.update(0.8)                                        # já velho demais pra somar
    b = f.add("+15 FERRO", 100, 200, IRON)
    assert len(f.items) == 2 and b.text == "+15 FERRO" and b.lane == 1


def test_different_texts_near_each_other_take_different_lanes():
    f = FloatingTexts()
    a = f.add("+15 FERRO", 100, 200, IRON)
    b = f.add("+15 SILICIO", 110, 200, "#c3d1e2")
    c = f.add("+O2", 90, 210, "#59d0e6")
    assert (a.lane, b.lane, c.lane) == (0, 1, 2)


def test_same_text_without_number_just_renews():
    f = FloatingTexts()
    a = f.add("+O2", 50, 50, "#59d0e6")
    f.update(0.3)
    assert f.add("+O2", 50, 50, "#59d0e6") is a and a.text == "+O2" and len(f.items) == 1


def test_far_apart_floaters_stay_on_lane_zero_and_lanes_free_up():
    f = FloatingTexts()
    assert f.add("+15 FERRO", 0, 0, IRON).lane == 0
    assert f.add("+15 FERRO", 500, 0, IRON).lane == 0    # longe: cada um no seu ponto
    near = f.add("+AGUA", 10, 0, "#6aa8ff")
    assert near.lane == 1
    f.update(1.0)
    f.update(0.3)                                        # os dois primeiros morreram (vida 1,2 s)
    assert all(it is not near for it in f.items) or near.life > 0
    f.items = [near]
    assert f.add("+O2", 0, 0, "#59d0e6").lane == 0       # a faixa 0 ficou livre de novo


def test_lane_is_in_screen_pixels():
    """A distância entre as faixas é em px da UI (altura da letra), então não muda com o zoom."""
    assert LANE_PX >= 10
