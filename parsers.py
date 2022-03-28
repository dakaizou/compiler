import collections
import dataclasses
from pprint import PrettyPrinter
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple, Union, cast

import bnf
from grammar import EOF, EPSILONG, Grammar, LRProduction, NonTerminal, Production, Symbol, Terminal
import scanner


class LL1Parser:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self.grammar.remove_direct_left_recursion()
        self.index_by_production: Dict[Production, int] = {}
        self.productions = []
        for i, production in enumerate(grammar.productions):
            self.productions.append(production)
            self.index_by_production[production] = i
        self.build_parsing_table()

    def build_parsing_table(self):
        self.parse_table: Dict[NonTerminal, Dict[Terminal, int]] = collections.defaultdict(dict)
        for production in self.grammar.productions:
            for terminal in self.grammar.first(production.rhs) - {EPSILONG}:
                if terminal in self.parse_table[production.lhs]:
                    raise RuntimeError("Ambiguous grammar detected")
                self.parse_table[production.lhs][terminal] = self.index_by_production[production]

            # TODO: slides(194/318) seems to be inside the inner loop?
            if EPSILONG in self.grammar.first(production.rhs):
                for terminal in self.grammar.follow_for[production.lhs.image]:
                    if terminal in self.parse_table[production.lhs]:
                        raise RuntimeError("Ambiguous grammar detected")
                    self.parse_table[production.lhs][terminal] = self.index_by_production[production]

    def parse(self, tokens: Iterable[Terminal]):
        stack: List[Symbol] = [EOF, self.grammar.start]
        token_iter = iter(tokens)
        sym = next(token_iter)
        resulting_productions = []

        while True:
            top = stack.pop()
            if top == sym == EOF:
                return resulting_productions

            if isinstance(top, Terminal):
                if top != sym:
                    print(f"{sym} found where {top} was expected")
                sym = next(token_iter)

            if isinstance(top, NonTerminal):
                if sym not in self.parse_table[top]:
                    print(f"No production found for {top} and {sym}")
                    continue
                production = self.productions[self.parse_table[top][sym]]
                resulting_productions.append(production)
                for symbol in reversed(production.rhs):
                    if symbol == EPSILONG:
                        continue
                    stack.append(symbol)


@dataclasses.dataclass(frozen=True)
class LRAction:
    pass


@dataclasses.dataclass(frozen=True)
class Accept(LRAction):
    pass


@dataclasses.dataclass(frozen=True)
class Shift(LRAction):
    target: int


@dataclasses.dataclass(frozen=True)
class Reduce(LRAction):
    target: int


class LR1Parser:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar
        self.augment_grammar()
        self.index_by_production: Dict[Production, int] = {}
        self.productions: List[Production] = []
        self.production_by_lhs: Dict[NonTerminal, Set[Production]] = collections.defaultdict(set)
        for i, production in enumerate(self.grammar.productions):
            self.productions.append(production)
            self.index_by_production[production] = i
            self.production_by_lhs[production.lhs].add(production)

        self.state_children: Dict[Tuple[int, Symbol], Set[int]] = collections.defaultdict(set)
        self.symbol_by_state: Dict[int, Set[Symbol]] = collections.defaultdict(set)
        self.action_table: Dict[int, Dict[Terminal, LRAction]] = collections.defaultdict(dict)
        self.goto_table: Dict[int, Dict[NonTerminal, int]] = collections.defaultdict(dict)
        self.cc: Dict[FrozenSet[LRProduction], int] = {}
        self.build_parsing_table()

    def build_parsing_table(self):
        self.calculate_canonical_collection()
        for state, state_index in self.cc.items():

            for item in state:
                # for Sk contains accepting item, Action[k, #] = accept
                if self.accepting_item == item:
                    self.action_table[state_index][EOF] = Accept()
                    continue

                if item.is_finished:
                    self.action_table[state_index][item.lookahead] = Reduce(self.index_by_production[item.p])

            for sym in self.symbol_by_state[state_index]:
                for child_index in self.state_children[(state_index, sym)]:
                    # goto(Si, a) = Sj => Action[i, a] = j
                    if isinstance(sym, Terminal):
                        self.action_table[state_index][sym] = Shift(child_index)

                    # goto(Si, Y) = Sj => Goto[i, Y] = j
                    if isinstance(sym, NonTerminal):
                        self.goto_table[state_index][sym] = child_index

    def calculate_canonical_collection(self):
        # i.e. all possible states
        state = self.closure({self.kernel})
        unvisited = {state}
        self.cc[state] = 0

        while unvisited:
            state = unvisited.pop()
            syms = set(item.current_symbol for item in state)
            syms.discard(None)

            for sym in syms:
                sym = cast(Symbol, sym)
                new_state = self.goto(state, sym)
                if new_state not in self.cc:
                    unvisited.add(new_state)
                    self.cc[new_state] = len(self.cc)
                self.state_children[(self.cc[state], sym)].add(self.cc[new_state])
                self.symbol_by_state[self.cc[state]].add(sym)
                # print(f'goto({self.cc[state]}, {sym}) = {self.cc[new_state]}')

    def parse(self, tokens):
        stack: List[Union[int, Symbol]] = [0]
        result = []
        action = None
        sym = next(tokens)
        while True:
            action = self.action_table[stack[-1]][sym] # type: ignore
            result.append(action)
            if isinstance(action, Shift):
                stack.append(sym)
                stack.append(action.target)
                sym = next(tokens)

            elif isinstance(action, Reduce):
                production = self.productions[action.target]
                for _ in range(2*len(production)):
                    stack.pop()
                next_state = self.goto_table[stack[-1]][production.lhs] # type: ignore
                stack.append(production.lhs)
                stack.append(next_state)

            elif isinstance(action, Accept):
                return result

            else:
                raise RuntimeError(f"Error encounter when {stack} on {sym}")

    def closure(self, productions: Set[LRProduction]) -> FrozenSet[LRProduction]:
        result: Set[LRProduction] = productions.copy()
        while True:
            len_before = len(result)
            productions = productions | result
            for production in productions:
                sym = production.current_symbol

                if sym is None or isinstance(sym, Terminal):
                    continue

                for p in self.production_by_lhs[cast(NonTerminal, sym)]:
                    for lookahead in self.grammar.first(production.get_beta() + (production.lookahead,)):
                        result.add(LRProduction(p.lhs, p.rhs, lookahead))

            if len_before == len(result):
                break
        return frozenset(result)

    def goto(self, productions: FrozenSet[LRProduction], symbol: Symbol):
        next_item_set = set()
        for p in productions:
            if p.current_symbol != symbol:
                continue
            if not p.is_finished:
                item = p.get_next()
                next_item_set.add(item)

        next_item_set.discard(None)
        return self.closure(next_item_set)

    def augment_grammar(self):
        start = NonTerminal(self.grammar.start.image + "'")
        p = Production(start, (self.grammar.start,))
        productions = {p}
        productions = productions.union(self.grammar.productions)
        symbols = self.grammar.symbols.union({start})
        self.grammar = Grammar(symbols, start, productions)
        self.kernel = LRProduction(p.lhs, p.rhs, EOF)
        self.accepting_item = self.kernel.get_next()
