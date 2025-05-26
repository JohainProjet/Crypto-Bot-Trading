def parse_ticker_stepsizes(filename: str) -> dict[str, dict[str, float]]:
    ticker_info = {}

    with open(filename, 'r') as file:
        for line in file:
            if not line.strip():
                continue

            symbol, values = line.split(':')
            symbol = symbol.strip()

            values = values.strip()
            stepsize = float(values.split('stepsize=')[1].split(',')[0])
            ticksize = float(values.split('ticksize=')[1])

            ticker_info[symbol] = {
                'step_size': stepsize,
                'tick_size': ticksize
            }

    return ticker_info
