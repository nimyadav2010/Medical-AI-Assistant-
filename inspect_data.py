import pandas as pd
import os

file_path = os.path.join("data", "records.xlsx")
try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    if 'Name' in df.columns:
        print("Names found in Excel:")
        print(df['Name'].tolist())
        print("Names (stripped):")
        print(df['Name'].astype(str).str.strip().tolist())
    else:
        print("'Name' column not found.")
except Exception as e:
    print(f"Error reading excel: {e}")
