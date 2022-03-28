from typing import Optional, Set, cast

import sly

from grammar import EPSILONG, GrammarJSONEncoder, NonTerminal, Symbol, Terminal, Production, Grammar


class Lexer(sly.Lexer):
    tokens = {NONTERMINAL, TERMINAL, DERIVE, SEP} # type: ignore
    DERIVE = r"::="
    NONTERMINAL = r"<[\w']+>"
    TERMINAL = r"[^:<;]"
    SEP = r";"
    ignore = " \t\r\n"

    def error(self, t):
        print("Illegal character '%s'" % t.value[0])
        self.index += 1


class Parser(sly.Parser):
    tokens = Lexer.tokens

    def __init__(self):
        self.symbols: Set[Symbol] = set()
        self.start: Optional[NonTerminal] = None

    @_('{ rule }') # type: ignore
    def rules(self, p):
        if self.start is None:
            raise RuntimeError("No start state found")
        return Grammar(self.symbols, self.start, set(p.rule))

    @_('NONTERMINAL DERIVE symbol { symbol } SEP') # type: ignore
    def rule(self, p): # type: ignore
        nonterminal = NonTerminal(p.NONTERMINAL.strip("<>"))
        self.symbols.add(nonterminal)
        if self.start is None:
            self.start = nonterminal
        return Production(nonterminal, (p.symbol0, *p.symbol1))  # type: ignore

    @_('NONTERMINAL DERIVE SEP') # type: ignore
    def rule(self, p):
        nonterminal = NonTerminal(p.NONTERMINAL.strip("<>"))
        if self.start is None:
            self.start = nonterminal
        self.symbols.add(nonterminal)
        self.symbols.add(EPSILONG)
        return Production(nonterminal, (EPSILONG,))  # type: ignore

    @_('TERMINAL') # type: ignore
    def symbol(self, p): # type: ignore
        terminal = Terminal(p.TERMINAL)
        self.symbols.add(terminal)
        return terminal

    @_('NONTERMINAL') # type: ignore
    def symbol(self, p):
        nonterminal = NonTerminal(p.NONTERMINAL.strip("<>"))
        self.symbols.add(nonterminal)
        return nonterminal


def parse(s: str) -> Grammar:
    lexer = Lexer()
    parser = Parser()
    return parser.parse(lexer.tokenize(s))


if __name__ == "__main__":
    example = """
        <E> ::= <E> + <T>;
        <E> ::= <T>;
        <T> ::= <T> * <F>;
        <T> ::= <F>;
        <F> ::= (<E>);
        <F> ::= n;
    """
    grammar: Grammar = cast(Grammar, parse(example))
    grammar.remove_direct_left_recursion()
    import json
    print(json.dumps(grammar.first_for, cls=GrammarJSONEncoder))
