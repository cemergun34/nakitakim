# -*- coding: utf-8 -*-
import sqlite3
import mysql.connector

MYSQL_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "iqdev21Nisan"
}

def main():
    mysql_conn = mysql.connector.connect(**MYSQL_CFG)
    mysql_cur = mysql_conn.cursor()

    sqlite_conn = sqlite3.connect('/Users/cemergun/NakitAkim/data/nakit_akim.db')
    sqlite_cur = sqlite_conn.cursor()

    tables = ['Subeler', 'cariHesaplar', 'faturalar', 'kategoriler', 'odemeSekli', 'VergiMuhtasar', 'hareketler']

    print("\n--- TOTAL ROW COUNT COMPARISON WITH HAREKETLER ---")
    for t in tables:
        # MySQL total count
        mysql_cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        my_cnt = mysql_cur.fetchone()[0]
        
        # SQLite total count
        try:
            sqlite_cur.execute(f"SELECT COUNT(*) FROM `{t}`")
            sq_cnt = sqlite_cur.fetchone()[0]
        except Exception as exc:
            sq_cnt = f"Error: {exc}"
            
        print(f"Table: {t:20} | MySQL Total: {my_cnt:<6} | SQLite Total: {sq_cnt}")

    mysql_cur.close()
    mysql_conn.close()
    sqlite_cur.close()
    sqlite_conn.close()

if __name__ == '__main__':
    main()
