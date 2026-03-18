import camelot
import pandas as pd
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# load env variables
load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# database connection
def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn


# create schema and table
def create_schema_and_table(conn):
    cursor = conn.cursor()

    # create schema bronze_layer
    cursor.execute("""
                   CREATE SCHEMA IF NOT EXISTS bronze_layer;
                   """)

    # create table supervisor_sale
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS bronze_layer.supervisor_sale (
                    cd_city TEXT,
                    sale TEXT,
                    cd_prd TEXT,
                    qty TEXT,
                    seller_id TEXT,
                    sale_date TEXT,
                    payment TEXT,
                    data_load TEXT,
                    CONSTRAINT unique_sale UNIQUE (sale));
                   """)
    conn.commit()
    cursor.close()

# store dataframe in the database
def store_dataframe(df, conn):
    cursor = conn.cursor()

    # all columns as string
    df = df.astype(str)

    for _, row in df.iterrows():
        cursor.execute(
            """
            INSERT INTO bronze_layer.supervisor_sale
                (cd_city, sale, cd_prd, qty, seller_id, sale_date, payment, data_load)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sale)
            DO UPDATE SET
                cd_city   = EXCLUDED.cd_city,
                cd_prd    = EXCLUDED.cd_prd,
                seller_id = EXCLUDED.seller_id,
                qty       = EXCLUDED.qty,
                payment   = EXCLUDED.payment,
                sale_date = EXCLUDED.sale_date,
                data_load = EXCLUDED.data_load
            WHERE
                bronze_layer.supervisor_sale.cd_city IS DISTINCT FROM EXCLUDED.cd_city
                OR bronze_layer.supervisor_sale.cd_prd IS DISTINCT FROM EXCLUDED.cd_prd
                OR bronze_layer.supervisor_sale.seller_id IS DISTINCT FROM EXCLUDED.seller_id
                OR bronze_layer.supervisor_sale.qty IS DISTINCT FROM EXCLUDED.qty
                OR bronze_layer.supervisor_sale.payment IS DISTINCT FROM EXCLUDED.payment
                OR bronze_layer.supervisor_sale.sale_date IS DISTINCT FROM EXCLUDED.sale_date;
            """,
            (
                row["cd_city"],
                row["sale"],
                row["cd_prd"],
                row["qty"],
                row["seller_id"],
                row["sale_date"],
                row["payment"],
                row["data_load"]
            )
        )
    conn.commit()
    cursor.close()

# capture pdf
def capture_pdf(path_pdf):
    tables = camelot.read_pdf(path_pdf, pages="all", flavor="stream")
    dfs = []

    for i, table in enumerate(tables):
        df = table.df

        if i == 0:
            df = df.iloc[2:]

        df = df.reset_index(drop=True)
        df = df.iloc[:, :6]

        df.columns = [
                        "cd_city",
                        "sale",
                        "cd_prd",
                        "qty",
                        "seller_id",
                        "sale_date_payment"
                     ]

        # sale_date and payment split
        split_cols = df["sale_date_payment"].str.strip().str.split(r"\s+", n=1, regex=True)

        df["sale_date"] = split_cols.str.get(0)
        df["payment"] = split_cols.str.get(1)

        df = df.drop(columns=["sale_date_payment"])
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)

# main
def bronze_layer_main():
    root_pdf_folder = r"/home/diego/airflow/dags/retail_ai_agent/bronze_layer/pdf/"
    conn = get_connection()

    create_schema_and_table(conn)

    supervisors = [
                    folder for folder in os.listdir(root_pdf_folder)
                    if os.path.isdir(os.path.join(root_pdf_folder, folder))
                  ]

    for supervisor_name in supervisors:
        folder_pdf = os.path.join(root_pdf_folder, supervisor_name)
        print(f"\nProcessing supervisor {supervisor_name}")

        for file in os.listdir(folder_pdf):
            if not file.endswith(".pdf"):
                continue

            path_pdf = os.path.join(folder_pdf, file)
            print(f"Capturing file {file}")

            df = capture_pdf(path_pdf)

            # data_load
            df["data_load"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            store_dataframe(df, conn)

    conn.close()
    print("Bronze layer stored successfully!")


if __name__ == "__main__":
    bronze_layer_main()