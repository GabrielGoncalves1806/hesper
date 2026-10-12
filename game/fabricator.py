"""Estado do menu do fabricador: aba aberta, receita selecionada e rolagem (Python puro, testado em
tests/test_fabricator.py; quem desenha é o ui.draw_fabricator e quem lê as teclas é o App).

Controles: A/D, ←/→ ou Tab trocam de aba (E não: E fecha o menu) · W/S ou ↑/↓ escolhem dentro da aba
(a lista rola junto) · a rodinha rola a lista sem mexer na seleção · clique na aba ou na receita.
Cada aba lembra a sua seleção e a sua rolagem.
"""

from game import config as C


def tab_kinds(tab_id: str) -> list[str]:
    """Receitas de uma aba, na ordem do MACHINE_ORDER."""
    return [k for k in C.MACHINE_ORDER if C.MACHINE_CATEGORY.get(k) == tab_id]


class FabMenu:
    def __init__(self, visible: int = C.FAB_VISIBLE_ROWS):
        self.visible = visible
        self.tab = 0
        self.selected = [0] * len(C.FAB_TABS)     # seleção de cada aba
        self.first = [0] * len(C.FAB_TABS)        # primeira linha visível de cada aba

    # ---- leitura
    @property
    def tab_id(self) -> str:
        return C.FAB_TABS[self.tab][0]

    @property
    def kinds(self) -> list[str]:
        return tab_kinds(self.tab_id)

    @property
    def current(self) -> str | None:
        kinds = self.kinds
        return kinds[self.selected[self.tab]] if kinds else None

    @property
    def max_first(self) -> int:
        return max(0, len(self.kinds) - self.visible)

    def window(self) -> list[tuple[int, str]]:
        """As receitas visíveis agora: [(índice na aba, tipo)]."""
        f = self.first[self.tab]
        return list(enumerate(self.kinds))[f:f + self.visible]

    # ---- ações
    def set_tab(self, index: int) -> None:
        self.tab = index % len(C.FAB_TABS)

    def switch_tab(self, step: int) -> None:
        self.set_tab(self.tab + step)

    def move(self, step: int) -> None:
        """W/S: anda na lista (dá a volta) e rola pra seleção ficar à vista."""
        n = len(self.kinds)
        if n:
            self.selected[self.tab] = (self.selected[self.tab] + step) % n
            self._follow()

    def scroll(self, step: int) -> None:
        """Rodinha: rola a lista (sem passar das pontas). A seleção não muda."""
        self.first[self.tab] = max(0, min(self.max_first, self.first[self.tab] + step))

    def select(self, kind: str) -> None:
        """Seleciona uma receita (clique), trocando de aba se precisar."""
        tab_id = C.MACHINE_CATEGORY.get(kind)
        ids = [t for t, _ in C.FAB_TABS]
        if tab_id in ids:
            self.tab = ids.index(tab_id)
            self.selected[self.tab] = self.kinds.index(kind)
            self._follow()

    def _follow(self) -> None:
        sel, f = self.selected[self.tab], self.first[self.tab]
        if sel < f:
            f = sel
        elif sel >= f + self.visible:
            f = sel - self.visible + 1
        self.first[self.tab] = max(0, min(self.max_first, f))
