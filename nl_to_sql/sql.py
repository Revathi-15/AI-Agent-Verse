import sqlite3
import pandas as pd
import os

def sanitize_column_names(df):
	df.columns=df.columns.str.replace(r'\W+','_',regex=True).str.strip()
	return df

db_path = "sqlite.db"

def csv_to_sqlite(csv_path, db_path):
    df = pd.read_csv(csv_path)
    df = sanitize_column_names(df)
    table_name = os.path.splitext(os.path.basename(csv_path))[0]
	
    conn=sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    conn.close()

    return table_name