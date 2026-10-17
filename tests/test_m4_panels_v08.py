"""v0.8 M4 · Task 7: os painéis do Microscópio e da Centrífuga no App (mock A, reports/design/v08_m4_paineis)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import ui as ui_mod  # noqa: E402
from game.app import INVENTORY_MODES, PANEL_MODES  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.systems import Machine  # noqa: E402
from tests.test_base_app import app, fresh  # noqa: E402,F401  (fixtures)
from tests.test_centrifuge_v08 import make_centrifuge  # noqa: E402
from tests.test_microscope_v08 import make_microscope  # noqa: E402


def open_mic(app, m):
    app.open_microscope = m
    app.set_mode("microscope")


def open_cent(app, m):
    app.open_centrifuge = m
    app.set_mode("centrifuge")


def draw_panel(app, m, status, info):
    ui = app.ui
    ui.begin()
    ui.draw_inventory(app.state.inventory, m, 0, app.renderer.item_icon, (0, 0), 0.0, None, status, info)
    return ui


# ---------------------------------------------------------------- modos, abrir e fechar
def test_modes_are_registered():
    for mode in ("microscope", "centrifuge"):
        assert mode in INVENTORY_MODES and mode in PANEL_MODES


def test_e_opens_each_panel(fresh, monkeypatch):
    import pygame
    s = fresh.state
    mic = make_microscope(s)
    monkeypatch.setattr(fresh, "e_target", lambda: ("microscope", mic))
    fresh.on_key(pygame.K_e)
    assert fresh.mode == "microscope" and fresh.open_microscope is mic
    fresh.set_mode("play")
    assert fresh.open_microscope is None
    cent = make_centrifuge(s)
    monkeypatch.setattr(fresh, "e_target", lambda: ("centrifuge", cent))
    fresh.on_key(pygame.K_e)
    assert fresh.mode == "centrifuge" and fresh.open_centrifuge is cent
    fresh.set_mode("play")
    assert fresh.open_centrifuge is None


def test_e_labels(fresh):
    s = fresh.state
    assert fresh.e_label(("microscope", make_microscope(s))) == "[E] Microscópio"
    assert fresh.e_label(("centrifuge", make_centrifuge(s))) == "[E] Centrífuga"


# ---------------------------------------------------------------- status de cada trava
def test_microscope_status(fresh):
    s = fresh.state
    m = make_microscope(s, ice=0)
    open_mic(fresh, m)
    assert fresh.microscope_status() == "Sem gelo"
    m.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 3)
    assert fresh.microscope_status() == "Analisando"
    m.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", max_stack("sample_rare"))
    assert fresh.microscope_status() == "Saída cheia"
    assert "nada" in fresh.microscope_info()
    fresh.set_mode("play")


def test_centrifuge_status_and_info(fresh):
    s = fresh.state
    m = make_centrifuge(s, algae=0, sample=None)
    open_cent(fresh, m)
    assert fresh.centrifuge_status() == "Sem alga"
    assert fresh.centrifuge_info() == "Alga + amostra = planta nova"
    m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 2)
    assert fresh.centrifuge_status() == "Sem amostra"
    m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_basic", 2)
    assert fresh.centrifuge_status() == "Girando"
    m.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = Stack("plant_1", max_stack("plant_1"))
    assert fresh.centrifuge_status() == "Saída cheia"
    fresh.set_mode("play")


# ---------------------------------------------------------------- recusas, clique e shift+clique
def test_microscope_refusals(fresh):
    m = make_microscope(fresh.state, ice=0)
    open_mic(fresh, m)
    st = m.storage
    assert fresh.panel_refusal(st, C.MIC_ICE_SLOT, "ice") is None
    assert fresh.panel_refusal(st, C.MIC_ICE_SLOT, "iron") == "O Microscópio só aceita gelo"
    for slot in C.MIC_OUT_SLOTS.values():
        assert fresh.panel_refusal(st, slot, "sample_basic") == "A saída só dá pra tirar"
    fresh.set_mode("play")


def test_centrifuge_refusals(fresh):
    m = make_centrifuge(fresh.state, algae=0, sample=("sample_basic", 1))
    open_cent(fresh, m)
    st = m.storage
    assert fresh.panel_refusal(st, C.CENT_ALGAE_SLOT, "algae") is None
    assert fresh.panel_refusal(st, C.CENT_ALGAE_SLOT, "ice") == "A Centrífuga só aceita alga e amostra"
    assert fresh.panel_refusal(st, C.CENT_SAMPLE_SLOT, "sample_basic") is None
    assert fresh.panel_refusal(st, C.CENT_SAMPLE_SLOT, "sample_rare") is not None        # um tipo por vez
    assert fresh.panel_refusal(st, C.CENT_SAMPLE_SLOT, "algae") == "A Centrífuga só aceita alga e amostra"
    for slot in C.CENT_OUT_SLOTS.values():
        assert fresh.panel_refusal(st, slot, "plant_1") == "A saída só dá pra tirar"
    fresh.set_mode("play")


def test_click_puts_ice_and_takes_a_sample(fresh):
    m = make_microscope(fresh.state, ice=0)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 2)
    open_mic(fresh, m)
    fresh.held = Stack("ice", 4)
    assert fresh.panel_put(m.storage, C.MIC_ICE_SLOT, 1) and m.storage.count("ice") == 4 and fresh.held is None
    fresh.held = Stack("iron", 1)
    assert not fresh.panel_put(m.storage, C.MIC_ICE_SLOT, 1)
    fresh.held = None
    assert fresh.panel_put(m.storage, C.MIC_OUT_SLOTS["sample_basic"], 1) and fresh.held == Stack("sample_basic", 2)
    fresh.held = None
    fresh.set_mode("play")


def test_shift_click_routes(fresh):
    s = fresh.state
    m = make_centrifuge(s, algae=0, sample=None)
    open_cent(fresh, m)
    s.inventory.slots[0] = Stack("algae", 3)
    s.inventory.slots[1] = Stack("ice", 3)
    s.inventory.slots[2] = Stack("sample_mutant", 2)
    ui = draw_panel(fresh, m, fresh.centrifuge_status(), fresh.centrifuge_info())
    rect = {(inv is s.inventory, i): r for r, inv, i in ui.slot_rects}
    fresh.panel_shift_click(rect[(True, 0)].center)
    fresh.panel_shift_click(rect[(True, 1)].center)
    fresh.panel_shift_click(rect[(True, 2)].center)
    assert m.storage.count("algae") == 3 and m.storage.count("ice") == 0 and m.storage.count("sample_mutant") == 2
    assert fresh.notice == "A Centrífuga só aceita alga e amostra"
    fresh.set_mode("play")


# ---------------------------------------------------------------- pegar tudo
def test_take_all_leaves_the_microscope_input(fresh):
    s = fresh.state
    m = make_microscope(s, ice=5)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 2)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", 1)
    open_mic(fresh, m)
    fresh.on_panel_button("take_microscope")
    assert s.inventory.count("sample_basic") == 2 and s.inventory.count("sample_rare") == 1
    assert m.storage.count("ice") == 5 and s.inventory.count("ice") == 0
    fresh.set_mode("play")


def test_take_all_leaves_the_centrifuge_inputs(fresh):
    s = fresh.state
    m = make_centrifuge(s, algae=4, sample=("sample_basic", 2))
    m.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = Stack("plant_1", 3)
    open_cent(fresh, m)
    fresh.on_panel_button("take_centrifuge")
    assert s.inventory.count("plant_1") == 3
    assert m.storage.count("algae") == 4 and m.storage.count("sample_basic") == 2
    fresh.set_mode("play")


# ---------------------------------------------------------------- desenho e seção DRONES
def test_microscope_panel_draws(fresh):
    s = fresh.state
    m = make_microscope(s, ice=3, chip=True)
    m.timer = C.MICROSCOPE_TIME * 0.6
    m.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 1)
    open_mic(fresh, m)
    fresh.ui.machine_art = fresh.panel_machine_art(m)
    assert fresh.ui.machine_art.get_size() == (40, 56)
    ui = draw_panel(fresh, m, fresh.microscope_status(), fresh.microscope_info())
    mine = [i for _, inv, i in ui.slot_rects if inv is m.storage]
    assert sorted(mine) == list(range(C.MIC_SLOTS))
    assert any(kind == "batch" for _, (kind, *_x) in ui.logistics_buttons) or not m.sends
    fresh.draw()                                                     # o frame inteiro, pelo App
    fresh.set_mode("play")


def test_centrifuge_panel_draws_with_and_without_sample(fresh):
    s = fresh.state
    m = make_centrifuge(s, algae=3, sample=("sample_mutant", 1), chip=True)
    m.storage.slots[C.CENT_OUT_SLOTS["plant_2"]] = Stack("plant_2", 1)
    open_cent(fresh, m)
    ui = draw_panel(fresh, m, fresh.centrifuge_status(), fresh.centrifuge_info())
    mine = [i for _, inv, i in ui.slot_rects if inv is m.storage]
    assert sorted(mine) == list(range(C.CENT_SLOTS))
    fresh.draw()
    m.storage.slots[C.CENT_SAMPLE_SLOT] = None                       # sem amostra: o cartão some
    fresh.draw()
    fresh.set_mode("play")


def task5_rules(monkeypatch):
    """As regras de drone da Task 5 (plano, tabela "Drones"), pro teste não depender dela: o Microscópio recebe gelo e
    manda as 3 amostras; a Centrífuga recebe alga + as 3 amostras e manda as 3 plantas."""
    from game import drones
    send, recv = drones.can_send, drones.can_receive
    plants = tuple(C.CENT_OUT_SLOTS)

    def can_send(m, item):
        if m.is_microscope:
            return item in C.SAMPLE_ITEMS
        if m.is_centrifuge:
            return item in plants
        return send(m, item)

    def can_receive(m, item):
        if m.is_microscope:
            return item == "ice"
        if m.is_centrifuge:
            return item == "algae" or item in C.SAMPLE_ITEMS
        return recv(m, item)

    monkeypatch.setattr(drones, "can_send", can_send)
    monkeypatch.setattr(drones, "can_receive", can_receive)


def test_drone_section_fits_the_panel_height(fresh, monkeypatch):
    """Com o chip e as regras da Task 5 (centrífuga recebe 4, os dois mandam 3), o painel cabe na tela lógica."""
    task5_rules(monkeypatch)
    ui = fresh.ui
    for m in (Machine(C.MICROSCOPE, 70, 70, chip=True), Machine(C.CENTRIFUGE, 70, 70, chip=True)):
        assert ui_mod.logi_row_cap(m) >= 4                           # 4 botões numa fileira, com o chip
        logi_y = ui_mod.MIC_LOGI_Y if m.is_microscope else ui_mod.CENT_LOGI_Y
        worst = 14 + 2 * ui_mod.LOGI_ROW + 2 + ui_mod.LOGI_BATCH_H
        assert ui.logistics_height(m) <= worst
        assert logi_y + worst + 10 <= 250                            # 248 / 244, como o Cultivador (244): cabe nos 270
    for m in (Machine(C.MICROSCOPE, 70, 70, chip=True), Machine(C.CENTRIFUGE, 70, 70, chip=True)):
        ui.begin()
        ui.draw_inventory(fresh.state.inventory, m, 0, fresh.renderer.item_icon, (0, 0), 0.0, None, "", None)
        bottom = max([r.bottom for r, _ in ui.logistics_buttons] + [r.bottom for r, _ in ui.chip_rects])
        assert bottom + 8 <= ui.h


# ---------------------------------------------------------------- eventos
def test_sample_and_centrifuge_events_show_floaters(fresh):
    s = fresh.state
    mic = make_microscope(s)
    cent = make_centrifuge(s)
    fresh.floaters.items.clear()
    fresh.on_game_event(("sample_found", mic, "sample_rare"))
    fresh.on_game_event(("centrifuge_done", cent, "plant_3"))
    fresh.on_game_event(("centrifuge_done", cent, None))
    fresh.on_game_event(("microscope_done", mic, None))              # nada: sem aviso
    assert [f.text for f in fresh.floaters.items] == ["+1 amostra rara", "+1 Lírio-de-Ilves", "falhou"]


def test_hover_text_of_the_machines(fresh, monkeypatch):
    s = fresh.state
    mic = make_microscope(s, ice=3)
    cent = make_centrifuge(s, algae=2, sample=("sample_basic", 1))
    monkeypatch.setattr(fresh, "hovered_prop", lambda: None)
    for m, head, label in ((mic, "Microscópio: 3 gelo", "[E] Microscópio"), (cent, "Centrífuga: 2 alga", "[E] Centrífuga")):
        kind = "microscope" if m.is_microscope else "centrifuge"
        monkeypatch.setattr(fresh, "hovered_machine", lambda m=m: m)
        monkeypatch.setattr(fresh, "e_target", lambda m=m, kind=kind: (kind, m))
        text = fresh.hint()
        assert text.startswith(head) and text.endswith("· [E] abrir"), text
