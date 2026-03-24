from retail_ai_agent.infrastructure.db import get_connection
from retail_ai_agent.utils.logger import log_error


# create schema and table
def create_structure():

    conn = get_connection()
    cur = conn.cursor()

    # create schema if not exists
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS gold_layer;
    """)

    # create fact table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gold_layer.sale_fact (
            sk_sale SERIAL PRIMARY KEY,

            sale VARCHAR,
            cd_city VARCHAR,
            city VARCHAR,
            region VARCHAR,

            sale_date TIMESTAMP,

            cd_seller VARCHAR,
            seller VARCHAR,
            gender VARCHAR,
            team_supervisor VARCHAR,

            cd_product VARCHAR,
            product VARCHAR,
            category VARCHAR,

            unit_value NUMERIC(10,2),
            qty INT,
            amount NUMERIC(12,2),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    # create unique key
    try:
        cur.execute("""
            ALTER TABLE gold_layer.sale_fact
            ADD CONSTRAINT uk_sale_fact
            UNIQUE (sale, cd_product, cd_seller);
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
 
    cur.close()
    conn.close()


# load
def load_sale_fact():

    conn = get_connection()
    cur = conn.cursor()

    query = """
    INSERT INTO gold_layer.sale_fact (
        sale,
        cd_city,
        city,
        region,
        sale_date,
        cd_seller,
        seller,
        gender,
        team_supervisor,
        cd_product,
        product,
        category,
        unit_value,
        qty,
        amount
    )
    SELECT 
        sp.sale, 
        sp.cd_city, 
        c.city, 
        c.region,
        sp.sale_date, 
        sp.cd_seller, 
        s.seller, 
        s.gender, 
        s.team_supervisor,
        sp.cd_product, 
        pd.product, 
        pd.category, 
        ROUND(pd.unit_value::numeric, 2),
        sp.qty,
        ROUND((pd.unit_value * sp.qty)::numeric, 2)
    FROM silver_layer.all_supervisor sp
    INNER JOIN city c ON c.cd_city = sp.cd_city
    INNER JOIN payment p ON p.cd_payment = sp.cd_payment
    INNER JOIN product pd ON pd.cd_product = sp.cd_product
    INNER JOIN seller s ON s.cd_seller = sp.cd_seller

    ON CONFLICT (sale, cd_product, cd_seller)
    DO UPDATE SET
        qty = EXCLUDED.qty,
        amount = EXCLUDED.amount,
        unit_value = EXCLUDED.unit_value;
    """

    cur.execute(query)
    print("Data loaded from Silver layer")
    conn.commit()
    cur.close()
    conn.close()
    print("sale_fact loaded successfully")

# main
def gold_layer_main():

    try:
        print("Starting the process of Gold layer\n")
        create_structure()
        load_sale_fact()
        
        print("Gold layer process finished successfully!")
    except Exception as e:
        log_error("gold_layer_main", "gold", str(e))
        raise


if __name__ == "__main__":
    gold_layer_main()