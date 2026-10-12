"""Fabricador com abas e rolagem (game/fabricator.py): categorias, troca de aba, seleção e scroll."""

from game import config as C
from game.fabricator import FabMenu, tab_kinds


def test_every_recipe_has_a_tab():
    ids = {t for t, _ in C.FAB_TABS}
    assert set(C.MACHINE_CATEGORY) == set(C.MACHINE_ORDER)
    assert set(C.MACHINE_CATEGORY.values()) <= ids
    assert tab_kinds("terraform") == ["o2", "melter", "heater", "o2_t2", "melter_t2", "heater_t2"]
    assert tab_kinds("energy") == ["solar"]
    assert tab_kinds("automation") == ["drill", "drone_station", "drone"]
    assert tab_kinds("storage") == ["chest"]
    assert tab_kinds("light") == ["lamp", "lamp_t2"]
    assert tab_kinds("suit") == ["o2_tank", "scanner"]                   # Marco 3: aba "Traje"


def test_switch_tab_wraps_and_remembers_selection():
    m = FabMenu()
    assert m.tab_id == "terraform" and m.current == "o2"
    m.move(1)
    assert m.current == "melter"
    m.switch_tab(1)
    assert m.tab_id == "energy" and m.current == "solar"
    m.switch_tab(-2)
    assert m.tab_id == "suit" and m.current == "o2_tank"
    m.switch_tab(-1)
    assert m.tab_id == "light" and m.current == "lamp"
    m.switch_tab(-1)
    assert m.tab_id == "storage" and m.current == "chest"
    m.switch_tab(3)
    assert m.tab_id == "terraform" and m.current == "melter"   # cada aba lembra a sua seleção


def test_move_wraps_and_scroll_follows_selection():
    m = FabMenu(visible=5)
    assert [k for _, k in m.window()] == tab_kinds("terraform")[:5]
    m.move(5)                                    # 6ª receita: a lista rola 1
    assert m.current == "heater_t2" and m.first[0] == 1
    m.move(1)                                    # dá a volta pro começo e rola de volta
    assert m.current == "o2" and m.first[0] == 0
    m.move(-1)
    assert m.current == "heater_t2" and m.first[0] == 1


def test_wheel_scroll_is_clamped_and_keeps_selection():
    m = FabMenu(visible=5)
    m.scroll(1)
    assert m.first[0] == 1 and m.current == "o2"
    m.scroll(10)
    assert m.first[0] == m.max_first == 1
    m.scroll(-10)
    assert m.first[0] == 0
    m.switch_tab(2)                              # automação: 3 receitas, nada pra rolar
    m.scroll(3)
    assert m.first[2] == 0


def test_select_by_click_changes_tab():
    m = FabMenu(visible=5)
    m.select("drone")
    assert m.tab_id == "automation" and m.current == "drone"
    m.select("heater_t2")
    assert m.tab_id == "terraform" and m.current == "heater_t2" and m.first[0] == 1
