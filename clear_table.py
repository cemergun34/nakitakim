from db.database import get_connection

def clear_kredi_karti():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM kredikartidata")
        conn.commit()
        print("kredikartidata table cleared successfully!")
    except Exception as e:
        print("ERROR:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    clear_kredi_karti()
