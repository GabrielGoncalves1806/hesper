"""Escuridão e luz da caverna (game/lighting.py)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import viewport
from game.lighting import Glint, LightSource, Lighting, helmet_lamp, lamp, ore_glints

WHITE = (255, 255, 255)


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()
    yield


def white(size=(320, 200)) -> pygame.Surface:
    s = pygame.Surface(size)
    s.fill(WHITE)
    return s


def lum(surf, pos) -> int:
    c = surf.get_at((int(pos[0]), int(pos[1])))
    return max(c.r, c.g, c.b)


def test_centro_da_luz_e_claro_e_longe_e_breu():
    target = white()
    cam = (1000, 500)
    Lighting().apply(target, cam, [LightSource(1160, 600, 64, WHITE)], ambient=0.0)
    assert lum(target, (160, 100)) >= 250            # centro: o mundo aparece inteiro
    assert lum(target, (5, 5)) == 0                  # longe: breu
    assert lum(target, (160 + 70, 100)) == 0         # logo depois do raio: breu


def test_borda_fica_entre_claro_e_escuro():
    target = white()
    Lighting().apply(target, (0, 0), [LightSource(160, 100, 64, WHITE)])
    assert 0 < lum(target, (160 + 52, 100)) < 200


def test_luz_fora_da_tela_nem_e_desenhada():
    lighting = Lighting()
    target = white()
    lighting.apply(target, (0, 0), [LightSource(2000, 2000, 64), LightSource(-300, 100, 64)])
    assert lighting._tex == {}                       # nenhuma textura pedida = culling funcionou
    assert lum(target, (0, 0)) == 0 and lum(target, (319, 199)) == 0


def test_luz_parcialmente_fora_da_tela_ainda_ilumina_a_borda():
    target = white()
    Lighting().apply(target, (0, 0), [LightSource(-20, 100, 64, WHITE)])
    assert lum(target, (2, 100)) > 0


def test_duas_luzes_somam_sem_estourar():
    single, double = white(), white()
    a = LightSource(140, 100, 64, WHITE, intensity=0.5)
    b = LightSource(180, 100, 64, WHITE, intensity=0.5)
    Lighting().apply(single, (0, 0), [a])
    Lighting().apply(double, (0, 0), [a, b])
    assert lum(double, (160, 100)) > lum(single, (160, 100))
    # muitas luzes no mesmo ponto: trava no máximo, o branco continua branco (não dá a volta)
    many = white()
    Lighting().apply(many, (0, 0), [LightSource(160, 100, 64, WHITE)] * 6)
    assert many.get_at((160, 100))[:3] == WHITE


def test_brilho_de_minerio_nao_ilumina_os_vizinhos():
    lighting = Lighting()
    target = white()
    lighting.apply(target, (0, 0), [])               # breu total
    lighting.draw_glints(target, (0, 0), [Glint(100, 100, (232, 160, 102))])
    assert lum(target, (100, 100)) > 0               # o pontinho aparece no escuro
    for p in ((106, 100), (94, 100), (100, 106), (100, 94), (110, 110)):
        assert lum(target, p) == 0                   # mas não clareia nada em volta


def test_brilho_de_minerio_some_no_claro():
    lighting = Lighting()
    target = pygame.Surface((320, 200))
    target.fill((40, 40, 40))
    lighting.apply(target, (0, 0), [LightSource(100, 100, 64, WHITE)])
    before = target.get_at((100, 100))
    lighting.draw_glints(target, (0, 0), [Glint(100, 100, (232, 160, 102))])
    assert target.get_at((100, 100)) == before


@pytest.mark.parametrize("zoom", [0.75, 1.0, 1.5, 2.0])
def test_coordenadas_com_zoom_e_camera(zoom):
    """Visão do App (960×540/zoom, 1 px = 1 px do mundo) com a câmera em qualquer lugar."""
    size = viewport.view_size(zoom)
    cam = (1234, 777)
    world_pt = (cam[0] + size[0] * 0.3, cam[1] + size[1] * 0.6)
    target = white(size)
    Lighting().apply(target, cam, [LightSource(*world_pt, 48, WHITE)])
    sx, sy = viewport.world_to_canvas(world_pt, cam, 1.0)
    assert lum(target, (sx, sy)) >= 250
    assert lum(target, (sx + 60, sy)) == 0


def test_aplicar_direto_no_canvas_com_scale():
    """scale = zoom: aplicar no canvas 960×540 já esticado."""
    zoom, cam = 2.0, (500, 300)
    world_pt = (620, 400)
    target = white((960, 540))
    Lighting().apply(target, cam, [LightSource(*world_pt, 40, WHITE)], scale=zoom)
    sx, sy = viewport.world_to_canvas(world_pt, cam, zoom)
    assert lum(target, (sx, sy)) >= 250
    assert lum(target, (sx + 40 * zoom + 8, sy)) == 0


def test_grade_presa_no_mundo():
    """Andar a câmera 1 px move o mapa inteiro 1 px junto (o contorno não 'treme')."""
    light = [LightSource(160, 100, 64, WHITE)]
    a, b = white(), white()
    Lighting().apply(a, (0, 0), light)
    Lighting().apply(b, (1, 0), light)
    for x in range(40, 280, 3):
        assert a.get_at((x, 100)) == b.get_at((x - 1, 100))


def test_luz_ambiente():
    full, half = white(), white()
    Lighting().apply(full, (0, 0), [], ambient=1.0)
    Lighting().apply(half, (0, 0), [], ambient=0.5)
    assert full.get_at((10, 10))[:3] == WHITE
    assert 120 <= lum(half, (10, 10)) <= 135
    tinted = white()
    Lighting().apply(tinted, (0, 0), [], ambient=(20, 30, 60))
    assert tinted.get_at((10, 10))[:3] == (20, 30, 60)


def test_banding_tem_poucos_niveis_e_suave_tem_muitos():
    def levels(banding):
        target = white((400, 200))
        Lighting(banding=banding).apply(target, (0, 0), [LightSource(200, 100, 160, WHITE)])
        return {lum(target, (x, 100)) for x in range(200, 400)}
    assert len(levels(True)) <= 5                    # 4 anéis + breu
    assert len(levels(False)) > 8


def test_flicker_e_cache_finito():
    lighting = Lighting()
    target = white()
    lights = [LightSource(160, 100, 64, WHITE, flicker=0.3)]
    for i in range(300):
        lighting.apply(target, (0, 0), lights, t=i / 60)
    assert len(lighting._tex) <= 17                  # intensidade quantizada: no máximo 17 texturas


def test_fabricas_dos_tipos_de_luz():
    head = helmet_lamp(100, 100, "right")
    assert head.x > 100 and head.y == 100 and head.radius == 4 * 32
    assert lamp(3, 4).radius == 5 * 32


def test_ore_glints_so_em_minerio():
    from game import config as C
    from game.world import World
    world = World.generate(7)
    glints = ore_glints(world, 0, 127, 0, 127)
    assert glints
    for g in glints:
        assert world.get(int(g.x // 32), int(g.y // 32)) in C.ORE_TILES
