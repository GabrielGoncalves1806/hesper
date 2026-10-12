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
    assert len(f.items) == 2 and b.text == "+15 FERRO" and b.lane >= 1
    assert _screen_gap(f) >= LANE_PX


def test_different_texts_near_each_other_take_different_lanes():
    f = FloatingTexts()
    a = f.add("+15 FERRO", 100, 200, IRON)
    b = f.add("+15 SILICIO", 110, 200, "#c3d1e2")
    c = f.add("+O2", 90, 210, "#59d0e6")
    assert (a.lane, b.lane) == (0, 1) and c.lane >= 2
    assert _screen_gap(f) >= LANE_PX                       # ninguém encosta em ninguém na tela


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


def test_neighbors_a_text_width_apart_take_another_lane():
    """Marco 4 (print drones_estacao): "+AGUA" nascendo ~70 px ao lado de um "+11 FERRO" encavalava."""
    f = FloatingTexts()
    a = f.add("+11 FERRO", 300, 200, IRON)
    b = f.add("+AGUA", 230, 205, "#6aa8ff")
    assert a.lane != b.lane


def test_older_floater_that_rose_into_the_line_takes_a_lane():
    """Marco 4 (print zoom_out): "+AGUA" nascido 20 px abaixo subiu até a linha do "+15 FERRO" novo."""
    f = FloatingTexts()
    old = f.add("+AGUA", 300, 260, "#6aa8ff")
    f.update(0.9)                                   # subiu ~20 px
    new = f.add("+15 FERRO", 220, 240, IRON)
    assert abs(old.y - new.y) < 4 and old.lane != new.lane


def _screen_gap(f):
    """Menor distância vertical na tela (px da UI) entre dois floaters vizinhos."""
    ys = sorted(it.y * f.scale - it.lane * LANE_PX for it in f.items)
    return min(b - a for a, b in zip(ys, ys[1:]))


def test_lanes_follow_the_zoom():
    """No zoom 0,75 (escala menor) dois floaters 60 px do mundo acima/abaixo já não encostam."""
    f = FloatingTexts()
    f.scale = 0.375
    f.add("+O2", 100, 200, "#59d0e6")
    assert f.add("+AGUA", 100, 240, "#6aa8ff").lane == 0         # 15 px da UI abaixo: não encosta
    f.scale = 1.0
    f.items.clear()
    f.add("+O2", 100, 200, "#59d0e6")
    assert f.add("+AGUA", 100, 205, "#6aa8ff").lane == 2        # 5 px abaixo: sobe 2 faixas pra passar
