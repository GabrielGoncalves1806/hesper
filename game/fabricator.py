"""Estado do menu do fabricador: aba aberta, receita selecionada e rolagem (Python puro, testado em
tests/test_fabricator.py; quem desenha é o ui.draw_fabricator e quem lê as teclas é o App).

Controles: A/D, ←/→ ou Tab trocam de aba (E não: E fecha o menu) · W/S ou ↑/↓ escolhem dentro da aba
(a lista rola junto) · a rodinha rola a lista sem mexer na seleção · clique na aba ou na receita.
Cada aba lembra a sua seleção e a sua rolagem.

A aba Fabricar do Tab (fabricar em campo) usa o mesmo FabMenu, com uma aba só: o kit de campo (field_menu).
"""

from game import config as C


def tab_kinds(tab_id: str) -> list[str]:
    """Receitas de uma aba, na ordem do MACHINE_ORDER."""
    return [k for k in C.MACHINE_ORDER if C.MACHINE_CATEGORY.get(k) == tab_id]


def field_kinds(_tab_id: str = "field") -> list[str]:
    """Receitas do kit de campo (aba Fabricar do Tab), na ordem do C.FIELD_RECIPES."""
    return list(C.FIELD_RECIPES)


class FabMenu:
    def __init__(self, visible: int = C.FAB_VISIBLE_ROWS, tabs=C.FAB_TABS, kinds_of=tab_kinds):
        self.visible = visible
        self.tabs = tabs                         # ((id, rótulo), ...)
        self.kinds_of = kinds_of                 # id da aba -> receitas dela
        self.tab = 0
        self.selected = [0] * len(tabs)          # seleção de cada aba
        self.first = [0] * len(tabs)             # primeira linha visível de cada aba

    # ---- leitura
    @property
    def tab_id(self) -> str:
        return self.tabs[self.tab][0]

    @property
    def kinds(self) -> list[str]:
        return self.kinds_of(self.tab_id)

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
        self.tab = index % len(self.tabs)

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
        index = next((i for i, (t, _) in enumerate(self.tabs) if kind in self.kinds_of(t)), None)
        if index is not None:
            self.tab = index
            self.selected[self.tab] = self.kinds.index(kind)
            self._follow()

    def _follow(self) -> None:
        sel, f = self.selected[self.tab], self.first[self.tab]
        if sel < f:
            f = sel
        elif sel >= f + self.visible:
            f = sel - self.visible + 1
        self.first[self.tab] = max(0, min(self.max_first, f))


def field_menu() -> FabMenu:
    """Menu da aba Fabricar do Tab: uma aba só, com o kit de campo inteiro à vista (sem rolagem)."""
    return FabMenu(visible=len(C.FIELD_RECIPES), tabs=(("field", "Fabricar"),), kinds_of=field_kinds)
