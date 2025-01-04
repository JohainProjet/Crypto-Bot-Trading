from src.strategy.strat2.Strat_2_main import strategy2_main

def main(strategy : int, time_to_sleep : int):
    if strategy == 2:
        strategy2_main(time_to_sleep)
    else:
        print("Stratégie non implémentée.")
    return 0
if __name__ == '__main__':
    main(2, 5000)
    exit()

    #Ouvrir un websocket spécialement pour les monnaie buy dans le dataframe pour vérifier l'order book par exemple
    # (rajouter une prise en compte des coups de trransactions)

    #Si le volume ne suit pas et le nombre de transaction n'augmente aps on peut vendre directement au lieu d'attendre par exemple
    #changer pour ne pas afficher tout le tableau des transaction à chaque fois mais plutôt la dernière ligne. Faire également que ce soit possible de voir
    # ce qui est utilisé dans le save mais à des moments partiel du temps. Par exemple si le porgrmamme dure 10000 secondes, on coupe en 5 et on affichera la ligne qi va dans
    # results à ce moment là.