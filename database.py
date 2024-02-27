import os
import json
import logging
import psycopg2
from psycopg2 import OperationalError


with open('config.json', 'r') as file:
    config = json.load(file)


DB_NAME = config['database']['db_name']
DB_USER = config['database']['user']
DB_PASSWORD = config['database']['password']
DB_HOST = config['database']['host']
DB_PORT = config['database']['port']
DB_TABLE_NAME = config['database']['table_name']


def create_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        logging.info("Connected to the database")
        print("Connected to the database")
    except psycopg2.Error as e:
        logging.error(f"Database connection error: {e}")
        print(f"Error: {e}")
    return conn


def insert_data_into_postgres(conn, message, request):
    cursor = conn.cursor()
    try:
        # Construct the SQL INSERT query
        sql_query = f"""INSERT INTO {DB_TABLE_NAME} (item_name, item_amount, item_type, item_price, 
                                                                            availability, chat_id) 
                       VALUES (%s, %s, %s, %s, %s, %s)"""

        # Execute the SQL query with the data from the request object
        cursor.execute(sql_query, (
            request.item_name, request.item_amount, request.item_type, request.item_price, request.availability,
            message.chat.id))

        # Commit the transaction
        conn.commit()
        logging.info("Data inserted into Postgres database")
        print("Data inserted into Postgres database")
    except psycopg2.Error as e:
        logging.error(f"Error inserting data into Postgres database: {e}")
        print(f"Error inserting data into Postgres database: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()


def update_availability_in_database(conn, item, availability):
    cursor = conn.cursor()
    try:
        # Construct the SQL UPDATE query
        sql_query = f"""UPDATE {DB_NAME}.{DB_TABLE_NAME} 
                                SET availability = %s 
                                WHERE item = %s"""

        # Execute the SQL query to update availability status
        cursor.execute(sql_query, (availability, item))

        # Commit the transaction
        conn.commit()
        print("Availability status updated in Postgres database")
    except psycopg2.Error as e:
        print(f"Error updating availability status in Postgres database: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
