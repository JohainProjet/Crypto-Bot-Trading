import glob
import os
from datetime import datetime
from xml.etree import ElementTree

import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry
from tqdm.asyncio import tqdm_asyncio

bucket_url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def list_common_prefixes(session, bucket_url, prefix):
    # params = {
    #     'delimiter': '/',
    #     'prefix': prefix
    # }
    # async with session.get(bucket_url, params=params) as resp:
    #     data = await resp.text()
    #     root = ElementTree.fromstring(data)
    #     return [p.find('{http://s3.amazonaws.com/doc/2006-03-01/}Prefix').text
    #             for p in root.findall('.//{http://s3.amazonaws.com/doc/2006-03-01/}CommonPrefixes')]
    with open("list_all_pairs.txt", 'r', encoding='utf-8') as f:
        return [f"data/spot/monthly/klines/{ticker}/" for ticker in f.read().splitlines()]


async def download_files(client, interval, prefix, start_date, end_date):
    params = {'prefix': f"{prefix}{interval}/"}
    async with client.get(bucket_url, params=params) as resp:
        data = await resp.text()
        root = ElementTree.fromstring(data)

        symbol = prefix.split("/")[-2]
        folder_path = f"historical_datas_from_api/zip_klines/data/spot/monthly/klines/{symbol}/{interval}/{start_date.strftime('%Y-%m-%d')}-{end_date.strftime('%Y-%m-%d')}/"
        os.makedirs(folder_path, exist_ok=True)

        for content in root.findall('.//{http://s3.amazonaws.com/doc/2006-03-01/}Contents'):
            key = content.find('{http://s3.amazonaws.com/doc/2006-03-01/}Key').text
            # Extract date from filename (format: SYMBOL-1m-YYYY-MM.zip)
            if not key.endswith(".zip"):
                continue
            date_str = key.split("-")[-2:]
            file_year = int(date_str[0])
            file_month = int(date_str[1].split(".")[0])
            file_date = datetime(file_year, file_month, 1)

            if start_date > file_date or file_date > end_date:
                continue
            filename = key.split('/')[-1]
            file_url = f"{bucket_url}/{key}"
            async with client.get(file_url) as file_resp:
                content = await file_resp.read()
                with open(f"{folder_path}{filename}", "wb") as f:
                    f.write(content)


async def main():
    start_date = datetime(2025, 4, 1)
    end_date = datetime(2025, 4, 30)
    async with aiohttp.ClientSession() as session:
        retry_client = RetryClient(session, raise_for_status=False, retry_options=ExponentialRetry(attempts=5))
        tasks = []
        for interval in ["1m"]:
            print(f"Downloading data for interval {interval}, from {start_date} to {end_date}...")
            prefixes = list_common_prefixes(session, bucket_url, "data/spot/monthly/klines/")
            semaphore = asyncio.Semaphore(5)

            async def with_semaphore(task):
                async with semaphore:
                    return await task

            tasks.extend(
                [with_semaphore(download_files(retry_client, interval, prefix, start_date, end_date)) for prefix in
                 prefixes])
            await tqdm_asyncio.gather(*tasks)
            print("Done!")

def rename_folders():
    base_path = "historical_datas_from_api/zip_klines/data/spot/monthly/klines"
    for symbol_path in glob.glob(f"{base_path}/*"):
        for interval_path in glob.glob(f"{symbol_path}/*"):
            for folder in glob.glob(f"{interval_path}/*-*"):
                if '-' in os.path.basename(folder):
                    new_name = folder.replace('-', '_')
                    os.rename(folder, new_name)
if __name__ == "__main__":
    # import asyncio
    # 
    # asyncio.run(main())
    rename_folders()

