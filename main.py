from src.strategy.strat2.Strat_2_main import strategy2_main

def main(strategy : int, time_to_sleep : int):
    if strategy == 2:
        strategy2_main(time_to_sleep)
    else:
        print("Stratégie non implémentée.")
    return 0
if __name__ == '__main__':
    main(2, 1800)