"""Estado do menu do fabricador e do menu de construção: aba aberta, receita selecionada e rolagem (Python puro,
testado em tests/test_fabricator.py; quem desenha é o ui.draw_fabricator e quem lê as teclas é o App).

Controles: A/D, ←/→ ou Tab trocam de aba (E não: E fecha o menu) · W/S ou ↑/↓ escolhem dentro da aba
(a lista rola junto) · a rodinha rola a lista sem mexer na seleção · clique na aba ou na receita.
No fabricador, abaixo da lista fica a área "Diagramas" (os diagramas do inventário, cada um com o LER). Pelo teclado,
S passa do fim da lista pros diagramas (W volta), Enter lê o escolhido (`diag`: None = o foco está na lista).
Cada aba lembra a sua seleção e a sua rolagem. O lote (`batch`, ×1 ou ×5) vale pro menu todo: o seletor do
painel de detalhe escolhe, e o Shift segurado fabrica até 5 em qualquer caso.

v0.5 M1: o mesmo FabMenu serve os dois menus. O fabricador (`craft_menu`) só tem itens (o que não vai pro chão:
construtor, drone, equipamento), nas abas C.CRAFT_TABS. O menu do construtor (`build_menu`) tem as máquinas, nas
abas C.FAB_TABS.
"""

from game import config as C


def tab_kinds(tab_id: str) -> list[str]:
    """Receitas de uma aba (máquinas e itens), na ordem do MACHINE_ORDER."""
    return [k for k in C.MACHINE_ORDER if C.MACHINE_CATEGORY.get(k) == tab_id]


def craft_kinds(tab_id: str) -> list[str]:
    """Receitas do fabricador numa aba: só itens (o que não vai pro chão)."""
    return [k for k in tab_kinds(tab_id) if not C.MACHINES[k].placeable]


def build_kinds(tab_id: str) -> list[str]:
    """Máquinas do construtor numa aba: só o que vai pro chão."""
    return [k for k in tab_kinds(tab_id) if C.MACHINES[k].placeable]


class FabMenu:
    def __init__(self, visible: int = C.FAB_VISIBLE_ROWS, tabs=C.CRAFT_TABS, kinds_of=craft_kinds):
        self.visible = visible
        self.tabs = tabs                         # ((id, rótulo), ...)
        self.kinds_of = kinds_of                 # id da aba -> receitas dela
        self.tab = 0
        self.selected = [0] * len(tabs)          # seleção de cada aba
        self.first = [0] * len(tabs)             # primeira linha visível de cada aba
        self.diag: int | None = None             # diagrama com o foco do teclado (None = a lista de receitas)
        self.batch = 1                           # lote do botão FABRICAR: 1 ou C.CRAFT_BATCH (seletor ×1/×5)

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

    def move(self, step: int, diagrams: int = 0) -> None:
        """W/S: anda na lista (dá a volta) e rola pra seleção ficar à vista. Com `diagrams` > 0, o S no fim da
        lista entra nos diagramas, o W no 1º volta pra lista, e o W no topo da lista vai pro último diagrama."""
        n = len(self.kinds)
        if self.diag is not None:
            self.clamp_diag(diagrams)
        if self.diag is not None:
            nxt = self.diag + step
            if nxt < 0:
                self.diag = None
            elif nxt >= diagrams:
                self.diag = None
                self.selected[self.tab] = 0
                self._follow()
            else:
                self.diag = nxt
            return
        if diagrams and n:
            sel = self.selected[self.tab]
            if step > 0 and sel == n - 1:
                self.diag = 0
                return
            if step < 0 and sel == 0:
                self.diag = diagrams - 1
                return
        if n:
            self.selected[self.tab] = (self.selected[self.tab] + step) % n
            self._follow()

    def clamp_diag(self, diagrams: int) -> None:
        """Depois de ler (a lista de diagramas encolheu): o foco não fica fora dela."""
        if self.diag is not None and diagrams <= 0:
            self.diag = None
        elif self.diag is not None:
            self.diag = min(self.diag, diagrams - 1)

    def scroll(self, step: int) -> None:
        """Rodinha: rola a lista (sem passar das pontas). A seleção não muda."""
        self.first[self.tab] = max(0, min(self.max_first, self.first[self.tab] + step))

    def set_batch(self, amount: int) -> bool:
        """Seletor ×1/×5. Devolve True se mudou."""
        amount = C.CRAFT_BATCH if amount > 1 else 1
        changed = amount != self.batch
        self.batch = amount
        return changed

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


def craft_menu() -> FabMenu:
    """Menu do fabricador da cápsula: só itens (e, embaixo, os diagramas)."""
    return FabMenu(visible=C.CRAFT_VISIBLE_ROWS, tabs=C.CRAFT_TABS, kinds_of=craft_kinds)


def build_menu() -> FabMenu:
    """Menu do construtor (E com ele na mão): as máquinas, nas abas de categoria."""
    return FabMenu(tabs=C.FAB_TABS, kinds_of=build_kinds)
