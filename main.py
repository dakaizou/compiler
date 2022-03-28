import pprint
from typing import cast

from parsers import LR1Parser, Reduce
import bnf
import scanner
from grammar import Grammar

pp = pprint.PrettyPrinter(indent=4)

example = """
    <E> ::= <E> + <T>;
    <E> ::= <T>;
    <T> ::= <T> * <F>;
    <T> ::= <F>;
    <F> ::= (<E>);
    <F> ::= n;
"""
tokens = scanner.scan("25 + 21 * 4")

# example = """
#     <S> ::= <A> a;
#     <A> ::= b <B>;
#     <A> ::= c <B>;
#     <A> ::=;
#     <B> ::= c <A>;
#     <B> ::= d <B>;
#     <B> ::=;
# """
# tokens = scanner.scan("c d c b a")

# example = """
#     <S> ::= ( <L> );
#     <S> ::= a;
#     <L> ::= <L> , <S>;
#     <L> ::= <S>;
# """
# tokens = scanner.scan("( ( a ) )")
grammar: Grammar = cast(Grammar, bnf.parse(example))
parser = LR1Parser(grammar)
actions = parser.parse(tokens)
for action in reversed(actions):
    if isinstance(action, Reduce):
        print(parser.productions[action.target])
