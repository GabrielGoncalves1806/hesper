"""v0.6 Fundo M2: luz por região da caverna (game/cave_light.py)."""
import numpy as np

from game import cave_light as L
from game.geo import BASALT, PLATEAU, SALAR
from game.lighting import WARM_WHITE


class W:
    def __init__(self, region):
        self.cave_region = region


def test_table_matches_approved_values():
    t = L.load()
    assert t[PLATEAU]["ambient"] == (6, 7, 10) and t[PLATEAU]["helmet"] == WARM_WHITE
    assert t[BASALT]["ambient"] == (16, 4, 2) and t[BASALT]["helmet_intensity"] == 0.95   # o vermelho fica (dono)


def test_missing_file_falls_back_to_pitch_black(tmp_path):
    t = L.load(tmp_path / "nada.json")
    assert all(e["ambient"] == (0, 0, 0) and e["helmet"] == WARM_WHITE for e in t)


def test_weights_on_the_border_are_mixed():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = SALAR
    w = L.region_weights(reg, 10, 5, 2)
    assert np.isclose(w.sum(), 1) and w[PLATEAU] == 0.4 and w[SALAR] == 0.6
    assert L.region_weights(reg, 2, 5, 2)[PLATEAU] == 1


def test_light_snaps_on_enter_and_eases_after():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = BASALT
    world = W(reg)
    cl = L.CaveLight()
    cl.update(world, 2, 5, t=0.0)
    assert cl.ambient == (6, 7, 10)                         # entrou: na hora
    cl.update(world, 17, 5, t=0.1)
    mid = cl.ambient
    assert 3 < mid[0] < 34                                 # cruzou: a meio caminho
    for i in range(2, 40):
        cl.update(world, 17, 5, t=i * 0.1)
    assert cl.ambient == (16, 4, 2)


def test_helmet_colour_is_quantized():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = BASALT
    cl = L.CaveLight()
    cl.update(W(reg), 10, 5, t=0.0)
    assert all(c % 8 == 0 or c == 255 for c in cl.helmet)


def test_no_region_map_is_centre():
    cl = L.CaveLight()
    cl.update(W(None), 0, 0, t=0.0)
    assert cl.ambient == (6, 7, 10)
