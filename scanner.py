from typing import Iterator

from grammar import EOF, Terminal


def scan(input_string) -> Iterator[Terminal]:
    current_index = 0
    end = len(input_string)

    while current_index != end:
        if input_string[current_index].isspace():
            current_index += 1
            continue

        if not input_string[current_index].isdigit():
            yield Terminal(input_string[current_index])
            current_index += 1
            continue

        number_end = current_index
        while number_end != end and input_string[number_end].isdigit():
            number_end += 1
        yield Terminal("n")
        # yield input_string[current_index:number_end]
        current_index = number_end

    yield EOF


if __name__ == "__main__":
    for tok in scan("5 + 23 * 2"):
        print(tok)
