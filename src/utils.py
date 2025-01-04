def get_api_key():
    with open(r"C:\Users\aissa\OneDrive\Bureau\Johain\Informatique\github\Crypto-Bot-Trading\src\test_keys.txt") as f:
        lines = f.read().splitlines()
        api_key = lines[0][4:]
        api_secret = lines[1][7:]
    return api_key, api_secret