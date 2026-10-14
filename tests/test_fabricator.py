"""Fabricador e menu do construtor com abas e rolagem (game/fabricator.py): categorias, troca de aba, seleção e
scroll. v0.5 M1: o fabricador (`craft_menu`) só tem itens; as máquinas estão no construtor (`build_menu`)."""

from game import config as C
from game.fabricator import FabMenu, build_kinds, build_menu, craft_kinds, craft_menu, tab_kinds


def test_every_recipe_has_a_tab():
    ids = {t for t, _ in C.FAB_TABS} | {t for t, _ in C.CRAFT_TABS}
    assert set(C.MACHINE_CATEGORY) == set(C.MACHINE_ORDER)
    assert set(C.MACHINE_CATEGORY.values()) <= ids
    assert tab_kinds("terraform") == ["o2", "melter", "heater", "o2_t2", "melter_t2", "heater_t2"]
    assert tab_kinds("energy") == ["solar"]
    assert tab_kinds("automation") == ["drill", "drone_station", "drone"]
    assert tab_kinds("storage") == ["chest"]
    assert tab_kinds("light") == ["lamp", "lamp_t2"]
    assert tab_kinds("suit") == ["o2_tank", "scanner"]                   # Marco 3: aba "Traje"
    assert tab_kinds("tools") == ["constructor"]                         # v0.5 M1


def test_craft_tabs_have_only_items_and_build_tabs_only_machines():
    assert craft_kinds("tools") == ["constructor"]
    assert craft_kinds("automation") == ["drone"]
    assert craft_kinds("suit") == ["o2_tank", "scanner"]
    assert build_kinds("automation") == ["drill", "drone_station"]
    for tab, _ in C.CRAFT_TABS:
        assert all(not C.MACHINES[k].placeable for k in craft_kinds(tab))
    for tab, _ in C.FAB_TABS:
        assert all(C.MACHINES[k].placeable for k in build_kinds(tab))


def test_switch_tab_wraps_and_remembers_selection():
    m = build_menu()
    assert m.tab_id == "terraform" and m.current == "o2"
    m.move(1)
    assert m.current == "melter"
    m.switch_tab(1)
    assert m.tab_id == "energy" and m.current == "solar"
    m.switch_tab(-2)
    assert m.tab_id == "light" and m.current == "lamp"
    m.switch_tab(-1)
    assert m.tab_id == "storage" and m.current == "chest"
    m.switch_tab(2)
    assert m.tab_id == "terraform" and m.current == "melter"   # cada aba lembra a sua seleção


def test_craft_menu_starts_on_the_constructor():
    m = craft_menu()
    assert m.tab_id == "tools" and m.current == "constructor"
    m.switch_tab(1)
    assert m.current == "drone"
    m.switch_tab(1)
    assert m.tab_id == "suit" and m.current == "o2_tank"


def test_move_wraps_and_scroll_follows_selection():
    m = FabMenu(visible=5, tabs=C.FAB_TABS, kinds_of=build_kinds)
    assert [k for _, k in m.window()] == tab_kinds("terraform")[:5]
    m.move(5)                                    # 6ª receita: a lista rola 1
    assert m.current == "heater_t2" and m.first[0] == 1
    m.move(1)                                    # dá a volta pro começo e rola de volta
    assert m.current == "o2" and m.first[0] == 0
    m.move(-1)
    assert m.current == "heater_t2" and m.first[0] == 1


def test_wheel_scroll_is_clamped_and_keeps_selection():
    m = FabMenu(visible=5, tabs=C.FAB_TABS, kinds_of=build_kinds)
    m.scroll(1)
    assert m.first[0] == 1 and m.current == "o2"
    m.scroll(10)
    assert m.first[0] == m.max_first == 1
    m.scroll(-10)
    assert m.first[0] == 0
    m.switch_tab(2)                              # automação: 2 máquinas, nada pra rolar
    m.scroll(3)
    assert m.first[2] == 0


def test_select_by_click_changes_tab():
    m = FabMenu(visible=5, tabs=C.FAB_TABS, kinds_of=build_kinds)
    m.select("drone_station")
    assert m.tab_id == "automation" and m.current == "drone_station"
    m.select("heater_t2")
    assert m.tab_id == "terraform" and m.current == "heater_t2" and m.first[0] == 1
    m.select("drone")                            # item: não está no construtor, nada muda
    assert m.current == "heater_t2"
