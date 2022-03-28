import collections
import dataclasses
import json
from typing import Dict, Optional, Set, Tuple


class GrammarJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, set):
            return list(o)
        return super().default(o)


@dataclasses.dataclass(frozen=True, order=True)
class Symbol:
    image: str


@dataclasses.dataclass(frozen=True, order=True)
class NonTerminal(Symbol):
    pass


@dataclasses.dataclass(frozen=True, order=True)
class Terminal(Symbol):
    pass


EPSILONG: Terminal = Terminal("<EPSILONG>")
EOF: Terminal = Terminal("<EOF>")


@dataclasses.dataclass(frozen=True, order=True)
class Production:
    lhs: NonTerminal
    rhs: Tuple[Symbol, ...]

    def __len__(self):
        return len(self.rhs)


@dataclasses.dataclass(frozen=True, order=True)
class LRProduction(Production):
    lookahead: Terminal
    # period is in front of rhs[cursor]
    cursor: int = 0

    @property
    def next(self):
        if self.cursor > len(self):
            return None
        return LRProduction(self.lhs, self.rhs, self.lookahead, self.cursor + 1)

    @property
    def current_symbol(self) -> Optional[Symbol]:
        if self.is_finished:
            return None
        return self.rhs[self.cursor]

    @property
    def beta(self):
        return self.rhs[self.cursor + 1:]

    @property
    def is_finished(self):
        return self.cursor >= len(self)

    @property
    def p(self):
        return Production(self.lhs, self.rhs)


@dataclasses.dataclass
class Grammar:
    symbols: Set[Symbol]
    start: NonTerminal
    productions: Set[Production]

    def __post_init__(self):
        self.calculate_first()
        self.calculate_follow()

    def remove_direct_left_recursion(self):
        left_recursions = []
        productionByLhs = collections.defaultdict(list)
        for production in self.productions:
            if production.rhs and production.lhs == production.rhs[0]:
                left_recursions.append(production)
                continue
            productionByLhs[production.lhs].append(production)

        # lr_production:
        # Y ::= YA
        # Y ::= B
        for lr_production in left_recursions:
            self.productions.remove(lr_production)
            new_image: str = lr_production.lhs.image + "'"
            while new_image in self.symbols:
                new_image += "'"
            new_lhs: NonTerminal = NonTerminal(new_image)
            self.symbols.add(new_lhs)

            # Y' ::= AY'
            self.productions.add(Production(
                new_lhs, lr_production.rhs[1:] + (new_lhs, )
            ))
            # Y' ::= <epsilong>
            self.productions.add(Production(
                new_lhs, (EPSILONG,)
            ))

            for production in productionByLhs[lr_production.lhs]:
                self.productions.remove(production)
                # Y ::= BY'
                self.productions.add(Production(
                    lr_production.lhs, production.rhs + (new_lhs, )
                ))

        self.calculate_first()
        self.calculate_follow()

    def to_json(self):
        return json.dumps(self, cls=GrammarJSONEncoder, indent=4, sort_keys=True)

    def calculate_first(self):
        # use Dict[str, Set[Terminal]] instead of Dict[Symbol, Set[Terminal]]
        # so that it's easier for json encoding
        self.first_for: Dict[str, Set[Terminal]] = collections.defaultdict(set)

        # first for a terminal is just itself
        for symbol in self.symbols:
            if isinstance(symbol, Terminal):
                self.first_for[symbol.image].add(symbol)

        # if there is epsilong production for NonTerminal X, add epsilong to first(X)
        for production in self.productions:
            if len(production) == 1 and production.rhs[0] == EPSILONG:
                self.first_for[production.lhs.image].add(EPSILONG)

        while True:
            revised = False

            for production in self.productions:
                image = production.lhs.image
                len_before = len(self.first_for[image])

                # add first(rhs) to first(lhs)
                self.first_for[image] |= self.first(production.rhs)

                if len_before != len(self.first_for[image]):
                    revised = True

            if not revised:
                break

    def first(self, rhs: Tuple[Symbol, ...]) -> Set[Terminal]:
        if len(rhs) == 0:
            # return set() or return {EPSILONG}?
            return set()

        current_first = self.first_for[rhs[0].image].copy()
        if isinstance(rhs[0], Terminal):
            current_first.add(rhs[0])

        for symbol in rhs[1:]:
            if EPSILONG not in current_first:
                break
            current_first.discard(EPSILONG)
            current_first |= self.first_for[symbol.image]
        return current_first

    def calculate_follow(self):
        # use Dict[str, Set[Terminal]] instead of Dict[Symbol, Set[Terminal]]
        # so that it's easier for json encoding
        self.follow_for: Dict[str, Set[Terminal]] = collections.defaultdict(set)

        # add # to follow of start
        self.follow_for[self.start.image].add(EOF)

        while True:
            revised = False

            for production in self.productions:
                for i, symbol in enumerate(production.rhs):
                    if isinstance(symbol, Terminal):
                        continue
                    len_before = len(self.follow_for[symbol.image])
                    next_first = self.first(production.rhs[i + 1:])
                    # add first(X1X2X3...) to follow(X0)
                    self.follow_for[symbol.image] |= next_first - {EPSILONG}

                    # if epsilong is in first(X1X2X3...) or if Xi is the last symbol
                    # add follow(Y) to follow(Xi)
                    if EPSILONG in next_first or i == len(production) - 1:
                        self.follow_for[symbol.image] |= self.follow_for[production.lhs.image]

                    if len_before != len(self.follow_for[symbol.image]):
                        revised = True

            if not revised:
                break
