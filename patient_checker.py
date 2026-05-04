import pandas as pd

file_name = "Compressed Raw Data/train.jsonl.gz"


#Reads first 5 rows of the file
df = pd.read_json(file_name, lines=True, compression="gzip", nrows=5)
print(df.head())

#loads in the first 5 patients and makes sure the load in correctly