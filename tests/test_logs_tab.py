"""Aba LOGs do inventário (Tab): cronologia (config.LOG_DAYS/LOG_ORDER), número exibido, lido/não lido/NOVO,
save com e sem o campo `logs_seen` e o clique que reabre a tela de leitura (e volta pra aba)."""

import os
import random
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game import settings  # noqa: E402
from game.systems import GameState  # noqa: E402
from game.ui import TAB_INVENTORY, TAB_LOGS  # noqa: E402

# índices em LOGS (nunca mudam: o save guarda índices) -> dia da história. 0..6 são os da v0.3; 7..18 são das
# estruturas (v0.7 M1: dias 1, 9, 22, 120, 152, 175, 198, 205, 219, 61, 209, 224)
DAY_3, DAY_97, DAY_212, DAY_188, DAY_140, DAY_41, DAY_230 = range(7)
N_LOGS = 24                                           # + 21..23 da VÉSPER-7 (v0.7 M4: dias 188, 190, 193)


# ---- cronologia e numeração ---------------------------------------------------------------------
def test_log_days_match_logs():
    assert len(C.LOG_DAYS) == len(C.LOGS) == len(C.LOG_TITLES) == N_LOGS
    for log, day in enumerate(C.LOG_DAYS):                # o texto começa com o dia certo
        assert C.LOGS[log].startswith(f"Dia {day}. "), log


def test_order_is_chronological():
    assert C.LOG_ORDER == [7, 19, DAY_3, 8, 9, DAY_41, 16, DAY_97, 10, DAY_140, 11, 20, 12, DAY_188, 21, 22, 23, 13,
                           14, 17, DAY_212, 15, 18, DAY_230]
    days = [C.LOG_DAYS[log] for log in C.LOG_ORDER]
    assert days == sorted(days)


def test_displayed_number_is_the_chronological_position():
    assert [C.log_label(log) for log in range(7)] == [
        "LOG 03", "LOG 08", "LOG 21", "LOG 14", "LOG 10", "LOG 06", "LOG 24"]
    assert sorted(C.log_number(log) for log in range(N_LOGS)) == list(range(1, N_LOGS + 1))


def test_terminal_title_uses_the_displayed_number():
    pygame.font.init()
    from game.ui import UI
    ui = UI()
    seen = []
    ui.text = lambda s, *a, **k: seen.append(s) or 0
    ui.draw_terminal(DAY_188, 0.0)
    assert seen[0] == f"{C.LOG_TITLES[DAY_188]} · LOG 14"


# ---- lido / não lido / NOVO ---------------------------------------------------------------------
def make_state() -> GameState:
    return GameState(rng=random.Random(1))


def test_entries_read_unread_and_new():
    s = make_state()
    s.read_log(DAY_3)
    s.read_log(DAY_188)
    s.reread_log(DAY_3)                                   # o do dia 3 já foi aberto pela aba
    entries = s.log_entries()
    assert [e[0] for e in entries] == C.LOG_ORDER
    assert [e[1] for e in entries] == list(range(1, N_LOGS + 1))
    read = {e[0] for e in entries if e[2]}
    new = {e[0] for e in entries if e[3]}
    assert read == {DAY_3, DAY_188} and new == {DAY_188} and s.new_logs == 1


def test_reread_clears_new_and_never_reveals_unread():
    s = make_state()
    s.read_log(DAY_41)
    assert s.reread_log(DAY_41) == C.LOGS[DAY_41]
    assert s.new_logs == 0 and DAY_41 in s.logs_seen
    assert s.reread_log(DAY_230) is None                  # não achado: a aba não abre
    assert DAY_230 not in s.logs_read and DAY_230 not in s.logs_seen


def test_row_text_hides_day_and_title_when_not_found():
    pygame.font.init()
    from game.ui import UI
    ui = UI()
    assert ui.log_row_text(DAY_212, 6, False) == "LOG 06 · ???"
    assert ui.log_row_text(DAY_212, 6, True) == f"LOG 06 · Dia 212 · {C.LOG_TITLES[DAY_212]}"


# ---- save ---------------------------------------------------------------------------------------
def test_save_roundtrip_keeps_seen():
    s = make_state()
    for log in (DAY_3, DAY_41, DAY_188):
        s.read_log(log)
    s.reread_log(DAY_41)
    loaded = save.state_from_dict(save.migrate(save.state_to_dict(s)))
    assert loaded.logs_read == {DAY_3, DAY_41, DAY_188} and loaded.logs_seen == {DAY_41}
    assert loaded.new_logs == 2


def test_v6_save_without_seen_treats_read_as_seen():
    """Save v6 de antes da aba LOGs (sem `logs_seen`): carrega, e os lidos não aparecem como NOVO."""
    s = make_state()
    s.read_log(DAY_3)
    s.read_log(DAY_97)
    data = save.state_to_dict(s)
    del data["progress"]["logs_seen"]
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.logs_seen == {DAY_3, DAY_97} and loaded.new_logs == 0


# ---- desenho nos 3 tamanhos ---------------------------------------------------------------------
@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
def test_logs_window_fits_and_rows_do_not_overlap(size):
    pygame.font.init()
    from game.ui import UI
    from game.inventory import Inventory
    ui = UI()
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = make_state()
    for log in (DAY_3, DAY_41, DAY_188):
        s.read_log(log)
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, lambda item: art.icon("iron"), (0, 0), equipment=s.equipment, state=s)
    inv_tabs = [r.copy() for r, _ in ui.inv_tab_rects]
    ui.begin()
    ui.draw_logs(s, 0, 0, (0, 0))
    assert [r.y for r, _ in ui.inv_tab_rects] == [r.y for r in inv_tabs]   # abas na mesma altura nas duas abas
    rows = [r for r, _ in ui.log_rows]
    found = {DAY_3, DAY_41, DAY_188}                      # com 19 LOGs a janela rola: só os da primeira página aparecem
    assert [lg for _, lg in ui.log_rows] == [lg for lg in C.LOG_ORDER[:ui.log_visible] if lg in found]
    w, h = ui.logs_window_size()
    assert w <= size[0] - 8 and 1 <= ui.log_visible <= len(C.LOGS)
    for a, b in zip(rows, rows[1:]):
        assert a.bottom <= b.top
    for r in rows:                                        # texto mais comprido cabe na linha (com o NOVO)
        assert 0 <= r.left and r.right <= size[0]
    longest = max(ui.body.size(ui.log_row_text(lg, n, True))[0] for n, lg in enumerate(C.LOG_ORDER, 1))
    tag_w = ui.font.size(ui.NEW_TAG)[0] + 6
    assert 6 + longest + 4 <= rows[0].w - 4 - tag_w
    assert rows[-1].bottom < ui.hotbar_y - 11 - 12        # lista e linha de ajuda acima da hotbar


# ---- clique: abre a leitura e volta pra aba ------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_logs_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def ui_center_to_window(app, rect):
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    return round(x + rect.centerx * k), round(y + rect.centery * k)


def click(app, rect):
    pos = ui_center_to_window(app, rect)
    app.mouse_window = pos
    app.mouse = app.window_to_canvas(pos)
    app.on_click(1)


def test_click_on_found_log_opens_reading_and_comes_back(app):
    s = app.state
    s.logs_read, s.logs_seen = {DAY_3, DAY_188}, {DAY_3}
    app.mode = "play"
    app.on_key(pygame.K_TAB)
    assert app.mode == "inventory" and app.inv_tab == TAB_INVENTORY
    app.draw()
    tab = next(r for r, i in app.ui.inv_tab_rects if i == TAB_LOGS)
    click(app, tab)
    assert app.inv_tab == TAB_LOGS and app.log_selected == C.LOG_ORDER.index(DAY_188)   # começa no NOVO
    app.draw()
    row = next(r for r, lg in app.ui.log_rows if lg == DAY_188)
    click(app, row)
    assert app.mode == "terminal" and app.terminal_index == DAY_188 and s.new_logs == 0
    app.on_key(pygame.K_e)                                # fecha a leitura: volta pra aba LOGs
    assert app.mode == "inventory" and app.inv_tab == TAB_LOGS
    app.on_key(pygame.K_TAB)
    assert app.mode == "play"


def test_unread_rows_are_not_clickable(app):
    s = app.state
    s.logs_read, s.logs_seen = {DAY_3}, {DAY_3}
    app.mode = "play"
    app.on_key(pygame.K_TAB)
    app.switch_inv_tab(TAB_LOGS)
    app.draw()
    assert [lg for _, lg in app.ui.log_rows] == [DAY_3]   # os ??? não entram no hit-test
    app.on_key(pygame.K_s)                                 # W/S pula os não achados (não tem outro lido)
    assert app.log_selected == C.LOG_ORDER.index(DAY_3)
    app.on_key(pygame.K_RETURN)
    assert app.mode == "terminal" and app.terminal_index == DAY_3
    app.on_key(pygame.K_ESCAPE)
    app.on_key(pygame.K_d)                                 # A/D troca a aba (D na última dá a volta)
    assert app.mode == "inventory" and app.inv_tab == TAB_INVENTORY
    app.on_key(pygame.K_ESCAPE)
    assert app.mode == "play"
