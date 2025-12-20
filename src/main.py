from .exchange_data import fetch_data

def main():
   
    df = fetch_data()
    print(df)        




if __name__ == '__main__':
    main()
