def get_api_key():
    with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\keys.txt") as f:
        api_key = f.readline()[4:]
        api_secret = f.readline()[7:]
    return api_key, api_secret