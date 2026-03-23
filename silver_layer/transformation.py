import pandas as pd
from datetime import datetime
from retail_ai_agent.db import get_connection

# main
def silver_layer_main():
    conn = get_connection()

    try:
        print("Starting the process of Silver layer\n")

        # read data from bronze
        df = pd.read_sql("SELECT * FROM bronze_layer.supervisor_sale", conn)
        print("Data loaded from Bronze layer")

        # rename columns
        df = df.rename(columns={
            "cd_prd": "cd_product",
            "payment": "cd_payment",
            "seller_id": "cd_seller"
        })

        # transformations

        # int
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
        df["cd_payment"] = pd.to_numeric(df["cd_payment"], errors="coerce")

        # date
        df["sale_date"] = pd.to_datetime(
            df["sale_date"], format="%d/%m/%y", errors="coerce"
        )

        # data_load
        df["data_load"] = datetime.now()

        print("Data transformed")

        with conn.cursor() as cursor:

            # create schema
            cursor.execute("CREATE SCHEMA IF NOT EXISTS silver_layer;")

            # create table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS silver_layer.all_supervisor (
                    cd_city TEXT,
                    sale TEXT,
                    cd_product TEXT,
                    qty INT,
                    cd_seller TEXT,
                    sale_date DATE,
                    cd_payment INT,
                    data_load TIMESTAMP
                );
            """)

            # truncate
            cursor.execute("TRUNCATE TABLE silver_layer.all_supervisor;")

            # insert
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO silver_layer.all_supervisor
                        (cd_city, sale, cd_product, qty, cd_seller, sale_date, cd_payment, data_load)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row["cd_city"],
                    row["sale"],
                    row["cd_product"],
                    row["qty"],
                    row["cd_seller"],
                    row["sale_date"],  
                    row["cd_payment"],
                    row["data_load"]
                ))

        conn.commit()

        print("all_supervisor loaded successfully")

        print("Silver layer process finished successfully")

    except Exception as e:
        conn.rollback() 
        print(f"Error: {e}")
        raise

    finally:
        conn.close() 


if __name__ == "__main__":
    silver_layer_main()