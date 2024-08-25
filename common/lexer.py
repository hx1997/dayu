class Lexer:
    def __init__(self, buf):
        self.buf = buf

    def next_token(self):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of Lexer instead of this abstract base')

    def eat(self, token):
        raise NotImplementedError(f'{self.__class__.__name__}: Use one of the subclasses of Lexer instead of this abstract base')
