import io
import pandas as pd

def test_pands_read():
    raw = "name,composition,price\nAugmentin 625, Amoxycillin (500mg) + Clavulanic Acid (125mg),201.2\n"
    df = pd.read_csv(io.StringIO(raw))
    df["composition"] = df["composition"].str.strip()
    assert  len(df)== 1
    assert df["name"].iloc[0] == "Augmentin 625"
    assert df["price"].iloc[0] > 200
    print(df.dtypes)
    assert df["composition"].iloc[0].startswith("Amoxycillin")
