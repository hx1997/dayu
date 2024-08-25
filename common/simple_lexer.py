from io import StringIO

from common.lexer import Lexer


class SimpleLexer(Lexer):
    def __init__(self, io: StringIO):
        if not isinstance(io, StringIO):
            raise TypeError(f'{self.__class__.__name__}: input is not a StringIO buffer')

        super().__init__(io)
        self.lines = self.buf.readlines()
        self.cur_line = 0
        self.token_iterator = self.iter_token()

    def iter_line(self, line_iter):
        tok = ''
        for ch in line_iter:
            if ch.strip(' ').strip('\t'):
                tok += ch
            elif tok:
                yield tok
                tok = ''
        yield tok

    def iter_token(self):
        while self.cur_line < len(self.lines):
            line = self.lines[self.cur_line]
            if not line.strip():
                self.cur_line += 1
                continue

            line_iter = iter(line)
            for tok in self.iter_line(line_iter):
                yield tok

            self.cur_line += 1

    def next_token(self):
        return next(self.token_iterator)

    def eat(self, token):
        return self.next_token() == token

    def read_until_token(self, token):
        read_content = ''
        next_token = self.next_token()
        read_content += next_token
        while next_token != token:
            read_content += ' '
            next_token = self.next_token()
            read_content += next_token
        return read_content

    def read_until_next_line(self, strip=True):
        read_content = ''
        next_token = self.next_token()
        read_content += next_token
        while not next_token.endswith('\n'):
            read_content += ' '
            next_token = self.next_token()
            read_content += next_token
        return read_content.strip() if strip else read_content
