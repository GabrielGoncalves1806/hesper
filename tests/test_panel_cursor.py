"""v0.6 M1 · Task 3: painéis de transferência com a pilha no cursor (clique pega/solta, direito metade/1,
Shift+clique manda direto). App headless; os cliques vão pelos retângulos que o painel desenhou."""

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import drones  # noqa: E402
from game import settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from tests.helpers import build_now  # noqa: E402

LEFT, RIGHT = 1, 3


@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_panel_cursor_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def fresh(app):
    app.set_mode("play")
    app.held = None
    app.keys_down.discard(pygame.K_LSHIFT)
    s = app.state
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.surface.machines[:] = []
    s.player.x, s.player.y = C.SPAWN_POS
    s.pop_events()
    return s


def open_panel(app, mode, obj):
    setattr(app, {"chest": "open_chest", "drill": "open_drill", "melter": "open_melter",
                  "smelter": "open_smelter", "dispenser": "open_dispenser", "station": "open_station", "crate": "open_crate"}[mode], obj)
    app.mode = mode
    app.draw()


def click(app, inv, index, button=LEFT):
    app.draw()
    rect = next(r for r, i, k in app.ui.slot_rects if i is inv and k == index)
    app.on_panel_click(button, rect.center)


def chest_panel(app, s, **items):
    chest = build_now(s, "chest", (s.player.tile[0] + 2, s.player.tile[1]))
    for item, n in items.items():
        chest.storage.add(item, n)
    s.inventory.slots[:] = [None] * len(s.inventory)
    open_panel(app, "chest", chest)
    return chest


def test_chest_click_picks_then_drops_where_chosen(app):
    s = fresh(app)
    chest = chest_panel(app, s, iron=20)
    click(app, chest.storage, 0)
    assert app.held == Stack("iron", 20) and chest.storage.slots[0] is None
    click(app, chest.storage, 5)                              # solta num slot escolhido do baú
    assert app.held is None and chest.storage.slots[5] == Stack("iron", 20)
    click(app, chest.storage, 5)
    click(app, s.inventory, 12)                               # ...e no inventário
    assert s.inventory.slots[12] == Stack("iron", 20) and app.held is None


def test_chest_join_swap_and_right_click(app):
    s = fresh(app)
    chest = chest_panel(app, s, iron=20)
    chest.storage.slots[1] = Stack("ice", 3)
    s.inventory.slots[9] = Stack("iron", 10)
    click(app, s.inventory, 9)
    click(app, chest.storage, 0)                              # mesmo item: junta
    assert chest.storage.slots[0] == Stack("iron", 30) and app.held is None
    click(app, chest.storage, 0)
    click(app, chest.storage, 1)                              # item diferente: troca
    assert chest.storage.slots[1] == Stack("iron", 30) and app.held == Stack("ice", 3)
    click(app, chest.storage, 2, RIGHT)                       # direito com a mão cheia: solta 1
    assert chest.storage.slots[2] == Stack("ice", 1) and app.held.count == 2
    app.held = None
    click(app, chest.storage, 1, RIGHT)                       # direito com a mão vazia: metade
    assert app.held == Stack("iron", 15) and chest.storage.slots[1] == Stack("iron", 15)


def test_shift_click_sends_straight(app):
    s = fresh(app)
    chest = chest_panel(app, s, iron=20)
    app.keys_down.add(pygame.K_LSHIFT)
    click(app, chest.storage, 0)
    assert app.held is None and s.inventory.count("iron") == 20 and chest.storage.is_empty()


def test_shift_click_sends_only_the_clicked_stack(app):
    """Dono (v0.6): Shift+clique manda só a pilha clicada, não todas as pilhas daquele item."""
    s = fresh(app)
    chest = chest_panel(app, s)
    s.inventory.slots[8] = Stack("iron", 10)
    s.inventory.slots[9] = Stack("iron", 7)
    app.keys_down.add(pygame.K_LSHIFT)
    try:
        click(app, s.inventory, 9)
    finally:
        app.keys_down.discard(pygame.K_LSHIFT)
    assert chest.storage.count("iron") == 7 and s.inventory.slots[8] == Stack("iron", 10)


def test_drill_refuses_drops_and_taking_counts_as_collected(app):
    s = fresh(app)
    drill = build_now(s, "drill", (s.player.tile[0] + 3, s.player.tile[1]))
    if drill is None:                                         # drill precisa de veio: monta a mão
        from game.systems import Machine
        drill = Machine("drill", s.player.tile[0] + 3, s.player.tile[1], resource="iron")
        s.surface.machines.append(drill)
    drill.stored = 12
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.slots[9] = Stack("iron", 4)
    open_panel(app, "drill", drill)
    click(app, s.inventory, 9)
    click(app, drill.storage, 0)                              # soltar na drill: recusa, pilha fica no cursor
    assert app.held == Stack("iron", 4) and drill.stored == 12 and "drill" in app.notice.lower()
    app.held = None
    before = s.drill_collected["iron"]
    s.pop_events()
    click(app, drill.storage, 0)                              # tirar pelo cursor
    assert app.held == Stack("iron", 12) and drill.stored == 0
    assert s.drill_collected["iron"] == before + 12
    assert any(e[0] == "drill_collect" for e in s.pop_events())


def test_melter_ice_in_only_ice_and_output_only_takes(app):
    s = fresh(app)
    m = build_now(s, "melter", (s.player.tile[0] + 3, s.player.tile[1]))
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.slots[9] = Stack("ice", 6)
    s.inventory.slots[10] = Stack("iron", 2)
    m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 2)
    open_panel(app, "melter", m)
    click(app, s.inventory, 10)
    click(app, m.storage, C.MELTER_ICE_SLOT)                  # ferro na entrada: recusa
    assert app.held == Stack("iron", 2) and m.storage.slots[C.MELTER_ICE_SLOT] is None
    click(app, s.inventory, 10)                               # devolve o ferro
    click(app, s.inventory, 9)
    click(app, m.storage, C.MELTER_CAPSULE_SLOT)              # gelo na saída: recusa
    assert app.held == Stack("ice", 6)
    click(app, m.storage, C.MELTER_ICE_SLOT)
    assert app.held is None and m.storage.slots[C.MELTER_ICE_SLOT] == Stack("ice", 6)
    click(app, m.storage, C.MELTER_CAPSULE_SLOT)              # a saída só tira
    assert app.held == Stack("water_capsule", 2)


def test_smelter_slots_ore_fuel_and_output_only_takes(app):
    s = fresh(app)
    m = build_now(s, "smelter", (s.player.tile[0] + 3, s.player.tile[1]))
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.slots[9] = Stack("iron", 6)
    s.inventory.slots[10] = Stack("magmatite", 3)
    s.inventory.slots[11] = Stack("copper", 2)
    s.inventory.slots[12] = Stack("ice", 2)
    m.storage.slots[C.SMELTER_OUT_SLOT] = Stack("iron_ingot", 2)
    open_panel(app, "smelter", m)
    click(app, s.inventory, 9)
    click(app, m.storage, C.SMELTER_FUEL_SLOT)                # ferro no combustível: recusa
    assert app.held == Stack("iron", 6) and m.storage.slots[C.SMELTER_FUEL_SLOT] is None
    click(app, m.storage, C.SMELTER_ORE_SLOT)                 # ferro na entrada: entra
    assert app.held is None and m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("iron", 6)
    click(app, s.inventory, 10)
    click(app, m.storage, C.SMELTER_ORE_SLOT)                 # magmatita na entrada: recusa
    assert app.held == Stack("magmatite", 3)
    click(app, m.storage, C.SMELTER_FUEL_SLOT)
    assert app.held is None and m.storage.slots[C.SMELTER_FUEL_SLOT] == Stack("magmatite", 3)
    click(app, s.inventory, 11)
    click(app, m.storage, C.SMELTER_ORE_SLOT)                 # cobre com ferro no slot: recusa e explica
    assert app.held == Stack("copper", 2) and m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("iron", 6)
    assert app.notice == "Tire o minério que está na Fundição antes"
    click(app, m.storage, C.SMELTER_OUT_SLOT)                 # a saída não aceita nada
    assert app.held == Stack("copper", 2) and m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 2)
    click(app, s.inventory, 11)                               # devolve o cobre
    click(app, s.inventory, 12)
    click(app, m.storage, C.SMELTER_ORE_SLOT)                 # gelo (v0.6 Fundo M4: o silício agora entra): recusa
    assert app.held == Stack("ice", 2) and app.notice == "A Fundição só aceita ferro, cobre, silício e magmatita"
    click(app, s.inventory, 12)
    click(app, m.storage, C.SMELTER_OUT_SLOT)                 # a saída só tira
    assert app.held == Stack("iron_ingot", 2)


def test_smelter_status_and_take_all(app):
    s = fresh(app)
    m = build_now(s, "smelter", (s.player.tile[0] + 3, s.player.tile[1]))
    open_panel(app, "smelter", m)
    assert app.smelter_status() == "SEM MINÉRIO"
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 3)
    assert app.smelter_status() == "SEM MAGMATITA"
    m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 1)
    assert app.smelter_status() == f"1 A CADA {C.SMELTER_TIME:g} S"
    m.storage.slots[C.SMELTER_OUT_SLOT] = Stack("copper_ingot", 1)
    assert app.smelter_status() == "SAÍDA OCUPADA"
    m.storage.slots[C.SMELTER_OUT_SLOT] = Stack("iron_ingot", 20)
    assert app.smelter_status() == "SAÍDA CHEIA"
    app.on_panel_button("take_smelter")
    assert s.inventory.count("iron") == 3 and s.inventory.count("magmatite") == 1 and s.inventory.count("iron_ingot") == 20
    assert m.storage.is_empty()


def test_dispenser_only_capsule(app):
    s = fresh(app)
    d = build_now(s, C.DISPENSER, (s.player.tile[0] + 3, s.player.tile[1]))
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.slots[9] = Stack("ice", 2)
    s.inventory.slots[10] = Stack("water_capsule", 3)
    open_panel(app, "dispenser", d)
    click(app, s.inventory, 9)
    click(app, d.storage, C.DISPENSER_CAPSULE_SLOT)
    assert app.held == Stack("ice", 2) and d.storage.is_empty()
    click(app, s.inventory, 9)
    click(app, s.inventory, 10)
    click(app, d.storage, C.DISPENSER_CAPSULE_SLOT)
    assert d.storage.slots[C.DISPENSER_CAPSULE_SLOT] == Stack("water_capsule", 3) and app.held is None


def test_station_one_drone_per_free_bay_refuses_other_items_and_busy_bays(app):
    s = fresh(app)
    st = build_now(s, "drone_station", (s.player.tile[0] + 3, s.player.tile[1]))
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.slots[9] = Stack("drone", 3)
    s.inventory.slots[10] = Stack("iron", 1)
    open_panel(app, "station", st)

    def bay(slot):
        app.draw()
        return next(r for r, k in app.ui.bay_rects if k == slot).center

    click(app, s.inventory, 10)
    app.on_panel_click(LEFT, bay(0))                          # ferro na baia: recusa
    assert app.held == Stack("iron", 1) and not st.station.drones
    click(app, s.inventory, 10)
    click(app, s.inventory, 9)
    app.on_panel_click(LEFT, bay(0))                          # 1 drone por baia; o resto fica na mão
    assert st.station.drone_in(0) is not None and app.held == Stack("drone", 2)
    app.on_panel_click(LEFT, bay(0))                          # baia ocupada: recusa
    assert app.held == Stack("drone", 2) and len(st.station.drones) == 1
    st.station.drone_in(0).state = drones.OUTBOUND   # em voo
    app.on_panel_click(LEFT, bay(0))
    assert app.held == Stack("drone", 2) and len(st.station.drones) == 1


def test_crate_take_via_cursor_emits_loot_and_closing_stashes(app):
    s = fresh(app)
    crate = s.crates[s.world.wrecks[0].crate]
    s.open_crate(crate)
    open_panel(app, "crate", crate)
    k = next(i for i, x in enumerate(crate.storage.slots) if x and x.item == "iron")
    n = crate.storage.slots[k].count
    s.pop_events()
    click(app, crate.storage, k)
    assert app.held.item == "iron" and app.held.count == n
    assert any(e[0] == "loot" for e in s.pop_events())
    s.inventory.slots[:] = [Stack("ice", 50) for _ in s.inventory.slots]       # inventário cheio
    app.set_mode("play")                                      # fecha: não cabe no inventário, vai pra caixa
    assert app.held is None and crate.storage.count("iron") >= n


def test_closing_with_held_returns_it_to_inventory(app):
    s = fresh(app)
    chest = chest_panel(app, s, iron=20)
    click(app, chest.storage, 0)
    app.set_mode("play")
    assert app.held is None and s.inventory.count("iron") == 20 and chest.storage.is_empty()
