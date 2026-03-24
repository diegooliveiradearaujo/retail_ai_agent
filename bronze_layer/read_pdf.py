import camelot
import pandas as pd
import os
from retail_ai_agent.infrastructure.db import get_connection
from datetime import datetime


# create schema and table
def create_schema_and_table(conn):
    with conn.cursor() as cursor:

        cursor.execute("""
                       CREATE SCHEMA IF NOT EXISTS bronze_layer;
                       """)

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


# store dataframe in database
def store_dataframe(df, conn):
    df = df.astype(str)

    with conn.cursor() as cursor:
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
    print("supervisor_sale loaded successfully")

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

        # split sale_date and payment
        split_cols = df["sale_date_payment"].str.strip().str.split(r"\s+", n=1, regex=True)

        df["sale_date"] = split_cols.str.get(0)
        df["payment"] = split_cols.str.get(1)

        df = df.drop(columns=["sale_date_payment"])
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)


# main
def bronze_layer_main():
    print("Starting the process of Bronze layer\n")
    root_pdf_folder = r"projects/retail_ai_agent/bronze_layer/pdf/"

    conn = get_connection() 

    try:
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

                # add load timestamp
                df["data_load"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                store_dataframe(df, conn)  

        print("Bronze layer process finished successfully")

    except Exception as e:
        conn.rollback()
        log_error("bronze_layer_main", "bronze", str(e))
        raise

    finally:
        conn.close()  


if __name__ == "__main__":
    bronze_layer_main()