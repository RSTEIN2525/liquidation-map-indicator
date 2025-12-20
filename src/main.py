from .exchange_data import fetch_data
from .entries import estimate_entries, Entry
from typing import List

def main():
   
    df = fetch_data()
    entries: List[Entry] = estimate_entries(df)

    for entry in entries:
        print(f"{entry.side} : {entry.price} : {entry.weight}")

if __name__ == '__main__':
    main()
