import sqlite3

conn = sqlite3.connect('results.db')
cursor = conn.cursor()

cursor.execute("""
               CREATE TABLE Results
               (
                   simulation_type  TEXT,
                   start_date       DATETIME,
                   end_date         DATETIME,
                   portfolio_values TEXT,
                   cash             REAL,
                   assets_value     REAL,
                   volume           REAL,
                   variation        REAL,
                   nb_of_trades     INTEGER,
                   stop_loss        REAL,
                   kline_type       TEXT,
                   PRIMARY KEY (Simulation_type, Start_date, End_date, volume, variation, nb_of_trades, stop_loss,
                                kline_type)
               );
               """)

conn.commit()
conn.close()
