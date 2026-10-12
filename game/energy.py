"""Energia global, sem fios (bíblia §8, Marco 2).

Tudo aqui é Python puro (nada de pygame), testado em tests/test_energy.py.

A ideia é bem simples, tipo a conta de luz de uma casa:
    produção = 5 kW da cápsula + 4 kW por painel solar
    consumo  = soma do que cada máquina colocada consome (tabela C.POWER_USE)
    fator    = min(1, produção / consumo)

Se a produção cobre o consumo, o fator é 1 e tudo roda normal. Se falta energia, NENHUMA
máquina desliga: todas rodam mais devagar, no mesmo ritmo. Ex.: 5 kW pra 8 kW de consumo
-> fator 0,625 -> as máquinas somam 62,5% do Ti e as drills extraem 62,5% do normal.

Como outro sistema usa isso (ex.: a estação de drones do Marco 3):
    - pra CONSUMIR energia: basta a máquina estar em C.POWER_USE (a estação já está lá, 3 kW);
    - pra saber o RITMO: `state.power.factor` (de 0 a 1) e multiplicar a velocidade por ele.
"""

from dataclasses import dataclass

from game import config as C


def machine_use(kind: str) -> float:
    """kW que uma máquina desse tipo consome (0 se não está na tabela)."""
    return C.POWER_USE.get(kind, 0)


def machine_gen(kind: str) -> float:
    """kW que uma máquina desse tipo gera (0 se não está na tabela)."""
    return C.POWER_GEN.get(kind, 0)


def starved(kind: str, factor: float) -> bool:
    """A máquina mostra o ícone de "sem energia" (raio vermelho piscando)? Só quem consome, e só
    quando o ritmo está abaixo de 100%. Painel solar, baú e drone nunca."""
    return machine_use(kind) > 0 and factor < 1.0


@dataclass(frozen=True)
class PowerReport:
    """Foto da energia num instante."""
    production: float     # kW gerados (cápsula + painéis)
    consumption: float    # kW pedidos pelas máquinas

    @property
    def factor(self) -> float:
        """Ritmo de todas as máquinas, de 0 a 1. Sem consumo nenhum, é 1."""
        if self.consumption <= 0:
            return 1.0
        return min(1.0, self.production / self.consumption)

    @property
    def deficit(self) -> bool:
        return self.consumption > self.production

    @property
    def level(self) -> str:
        """Cor do medidor: 'ok' (sobra), 'tight' (perto do limite) ou 'deficit'."""
        if self.deficit:
            return "deficit"
        if self.consumption >= C.ENERGY_TIGHT * self.production:
            return "tight"
        return "ok"


def power_report(kinds) -> PowerReport:
    """Soma produção e consumo. `kinds` = tipos das máquinas colocadas no mundo (ex.: ['o2', 'solar'])."""
    kinds = list(kinds)
    production = C.POD_POWER + sum(machine_gen(k) for k in kinds)
    consumption = sum(machine_use(k) for k in kinds)
    return PowerReport(production, consumption)


class PowerAlert:
    """Decide QUANDO tocar o som power_low (uma vez quando o déficit começa).

    Histerese: depois de tocar, o som só "rearma" quando o jogador passa ENERGY_REARM_TIME
    segundos seguidos sem déficit. Assim, colocar e tirar uma máquina na borda do limite
    não fica disparando o alarme toda hora.
    """

    def __init__(self):
        self.armed = True        # pode tocar no próximo déficit?
        self.ok_time = 0.0       # segundos seguidos sem déficit

    def update(self, deficit: bool, dt: float) -> bool:
        """Chame todo frame. Devolve True no frame em que o som deve tocar."""
        if deficit:
            self.ok_time = 0.0
            if self.armed:
                self.armed = False
                return True
            return False
        self.ok_time += dt
        if self.ok_time >= C.ENERGY_REARM_TIME:
            self.armed = True
        return False
