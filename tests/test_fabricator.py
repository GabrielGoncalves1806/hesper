"""Fabricador e menu do construtor com abas e rolagem (game/fabricator.py): categorias, troca de aba, seleção e
scroll. v0.5 M1: o fabricador (`craft_menu`) só tem itens; as máquinas estão no construtor (`build_menu`)."""

import random

from game import config as C
from game.fabricator import FabMenu, build_kinds, build_menu, craft_kinds, craft_menu, t2_kinds, tab_kinds
from game.inventory import Stack
from game.systems import GameState


def test_every_recipe_has_a_tab():
    ids = {t for t, _ in C.FAB_TABS} | {t for t, _ in C.CRAFT_TABS}
    assert set(C.MACHINE_CATEGORY) == set(C.MACHINE_ORDER)
    assert set(C.MACHINE_CATEGORY.values()) <= ids
    assert tab_kinds("terraform") == ["o2", "melter", "heater", "o2_t2", "melter_t2", "heater_t2"]
    assert tab_kinds("energy") == ["solar"]
    assert tab_kinds("automation") == ["drill", "drone_station", "drone", "smelter", "water_collector", "cultivator", "centrifuge", "workbench"]   # v0.6 M3: a Fundição; v0.8 M2: o Coletor de água; M3: o Cultivador; M4: a Centrífuga
    assert tab_kinds("storage") == ["chest_small", "chest", "chest_large"]
    assert tab_kinds("light") == ["lamp", "lamp_t2"]
    assert tab_kinds("materials") == ["wire", "circuit"]                         # v0.6 M3: fios saem do lingote de cobre
    assert tab_kinds("suit") == ["o2_tank", "scanner", "backpack"]       # Marco 3: aba "Traje" (a mochila é da T2)
    assert tab_kinds("tools") == ["constructor", "diagram_workbench", "diagram_chest_large"]                         # v0.5 M1


def test_craft_tabs_have_only_items_and_build_tabs_only_machines():
    assert craft_kinds("tools") == ["constructor", "diagram_workbench", "diagram_chest_large"]
    assert craft_kinds("automation") == []                   # v0.6 Fundo M5: o drone, o circuito, o tanque e o scanner
    assert craft_kinds("materials") == ["wire"]              # são da Bancada T2 (o T1 não mostra)
    assert craft_kinds("suit") == []
    assert build_kinds("automation") == ["drill", "drone_station", "smelter", "water_collector", "cultivator", "centrifuge", "workbench"]
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
    assert m.tab_id == "decor" and m.current == "prop_table"     # v0.7 M2: a aba "Decoração" é a última
    m.switch_tab(-1)
    assert m.tab_id == "base" and m.current == "base_floor"      # v0.5 M2: a "Base" vem antes dela
    m.switch_tab(-1)
    assert m.tab_id == "light" and m.current == "lamp"
    m.switch_tab(-1)
    assert m.tab_id == "storage" and m.current == "chest_small"
    m.switch_tab(4)
    assert m.tab_id == "terraform" and m.current == "melter"   # cada aba lembra a sua seleção


def test_craft_menu_starts_on_the_constructor():
    m = craft_menu()
    assert m.tab_id == "tools" and m.current == "constructor"
    assert [t for t, _ in m.tabs] == ["tools", "materials"]    # v0.6 Fundo M5: Automação e Traje esvaziaram (Bancada T2) e somem
    m.switch_tab(1)
    assert m.tab_id == "materials" and m.current == "wire"
    m.switch_tab(1)
    assert m.tab_id == "tools"


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
    m.switch_tab(1)                              # energia: 1 máquina, nada pra rolar (a automação já passou de 5 no v0.8 M3)
    m.scroll(3)
    assert m.first[1] == 0


def test_select_by_click_changes_tab():
    m = FabMenu(visible=5, tabs=C.FAB_TABS, kinds_of=build_kinds)
    m.select("drone_station")
    assert m.tab_id == "automation" and m.current == "drone_station"
    m.select("heater_t2")
    assert m.tab_id == "terraform" and m.current == "heater_t2" and m.first[0] == 1
    m.select("drone")                            # item: não está no construtor, nada muda
    assert m.current == "heater_t2"


def test_wire_recipe_in_materials_tab():
    assert ("materials", "Materiais") in C.CRAFT_TABS
    assert ("materials", "Materiais") not in C.FAB_TABS                  # o construtor não ganha a aba nova
    assert C.MACHINES["wire"].cost == {"copper_ingot": 1} and C.CRAFT_YIELD["wire"] == 3
    assert "wire" in craft_kinds("materials")


def test_crafting_wire_gives_three():
    g = GameState(rng=random.Random(1))                                  # nasce na base (o craft exige in_base_zone)
    g.inventory.add("copper_ingot", 2)
    assert g.craft("wire")
    assert g.inventory.count("wire") == 3 and g.inventory.count("copper_ingot") == 1
    assert g.crafted["wire"] == 1                                        # conta fabricações, não fios
    assert g.craft_many("wire") == 1 and g.inventory.count("wire") == 6 and not g.craft("wire")   # acabou o cobre


def test_crafting_wire_needs_room_for_all_three():
    g = GameState(rng=random.Random(1))
    g.inventory.slots[:] = [None] * len(g.inventory)
    for i in range(2, len(g.inventory)):                                 # tudo cheio; sobra só a pilha de fios quase cheia
        g.inventory.slots[i] = Stack("iron", 1)
    g.inventory.slots[0] = Stack("wire", C.STACK_LOOT - 2)
    g.inventory.slots[1] = Stack("copper_ingot", 2)                      # (o slot não esvazia ao gastar 1)
    assert not g.craft("wire") and g.inventory.count("copper_ingot") == 2   # 3 fios não cabem (só 2 de espaço)
    assert ("inv_full",) in g.events


def test_circuit_recipe_in_materials():
    m = C.MACHINES["circuit"]
    assert m.cost == {"wire": 3, "silicon": 5} and m.unlock_ti == 0     # v0.6 Fundo M5: 3 fios + 5 silício, na Bancada T2
    assert C.MACHINE_CATEGORY["circuit"] == "materials"
    assert "circuit" not in craft_kinds("materials") and "circuit" in t2_kinds("t2")


def test_crafting_circuit_from_silicon_and_wire_on_the_bench():
    g = GameState(rng=random.Random(1))
    g.inventory.add("silicon", 5)
    g.inventory.add("wire", 3)
    assert not g.craft("circuit")                                        # o T1 não fabrica o circuito
    assert g.craft("circuit", bench="t2")
    assert g.inventory.count("circuit") == 1
    assert g.inventory.count("silicon") == 0 and g.inventory.count("wire") == 0
