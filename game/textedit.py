"""Campo de texto de uma linha (nome do baú). Python puro, testado em tests/test_chest_name.py.

O App liga a digitação do SDL (pygame.key.start_text_input) só enquanto o campo está aberto e
passa pra cá o que chega:
    - evento TEXTINPUT  -> insert(texto)   (já vem com acento, maiúscula etc. resolvidos pelo sistema)
    - Backspace         -> backspace()
    - Enter / Esc       -> quem chama confirma (usa `text`) ou cancela (usa `original`)
O cursor fica sempre no fim (nome curto: não precisa de setinhas).
"""

from dataclasses import dataclass


@dataclass
class TextField:
    text: str
    max_len: int
    original: str = ""

    def __post_init__(self):
        self.text = self.text[:self.max_len]
        self.original = self.original or self.text

    def insert(self, chunk: str) -> None:
        """Acrescenta o que foi digitado (sem caractere de controle), até o limite."""
        chunk = "".join(ch for ch in chunk if ch.isprintable())
        self.text = (self.text + chunk)[:self.max_len]

    def backspace(self) -> None:
        self.text = self.text[:-1]

    @property
    def full(self) -> bool:
        return len(self.text) >= self.max_len
