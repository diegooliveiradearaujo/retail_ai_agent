from retail_ai_agent.infrastructure.db import get_connection

def log_error(process_name, layer, message):

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                            INSERT INTO public.log_process
                            (process_name, layer, message)
                            VALUES (%s, %s, %s)
                            """, (process_name, layer, message))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Log error failed: {e}")

    finally:
        conn.close()