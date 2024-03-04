import os
import json
import logging.config
import datetime
import psycopg2
from psycopg2 import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Item


logging.config.fileConfig('logging.ini')

# Create a logger specific to this module
# logger = logging.getLogger(__name__)

# Set the log level
# logger.setLevel(logging.DEBUG)

logging.debug('This is a test debug message')
logging.info('This is a test info message')
logging.error('This is a test error message')


with open('config.json', 'r') as file:
    config = json.load(file)

DB_URL = config['database']['db_url']
engine = create_engine(DB_URL, echo=True)

DB_NAME = config['database']['db_name']
DB_USER = config['database']['user']
DB_PASSWORD = config['database']['password']
DB_HOST = config['database']['host']
DB_PORT = config['database']['port']
DB_TABLE_NAME = config['database']['table_name']

Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)


def create_database_session():
    logging.info('DB Session was created')
    return DBSession()


def insert_item(session, message, request):
    try:
        item = Item(
            item_name=request.item_name,
            item_amount=request.item_amount,
            item_type=request.item_type,
            item_price=request.item_price,
            availability=request.availability,
            chat_id=message.chat.id,
            timestamp=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        )
        session.add(item)
        session.commit()
        logging.info("The item was inserted in the database")
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Error inserting data into database: {e}")
        print(f"Error inserting data into database: {e}")
        return False
    finally:
        session.close()


def get_items(session, item_name=None, start_date=None, end_date=None):
    query = session.query(Item)
    if item_name:
        query = query.filter(Item.item_name == item_name)
    if start_date and end_date:
        query = query.filter(Item.timestamp.between(start_date, end_date))
    return query.all()


def create_database_connection():
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


def insert_data_into_database(conn, message, request):
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    try:
        # Construct the SQL INSERT query
        sql_query = f"""INSERT INTO {DB_TABLE_NAME} (item_name, item_amount, item_type, item_price, 
                                                                            availability, chat_id, timestamp) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s)"""

        # Execute the SQL query with the data from the request object
        cursor.execute(sql_query, (
            request.item_name, request.item_amount, request.item_type, request.item_price, request.availability,
            message.chat.id, timestamp))

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
        logging.info("Availability status updated in Postgres database")
        print("Availability status updated in Postgres database")
    except psycopg2.Error as e:
        logging.error(f"Error updating availability status in Postgres database: {e}")
        print(f"Error updating availability status in Postgres database: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()


def get_data_from_database(conn):
    cursor = conn.cursor()
    try:
        # Construct the SQL SELECT query
        sql_query = f"""SELECT * FROM {DB_TABLE_NAME} (item_name, item_amount, item_type, item_price, 
                                                                                availability, chat_id, timestamp) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql_query, (
            request.item_name, request.item_amount, request.item_type, request.item_price, request.availability,
            message.chat.id, timestamp))
        conn.commit()
        logging.info("Data selected from Postgres database")
    except psycopg2.Error as e:
        logging.error(f"Error selecting data from Postgres database: {e}")
        conn.rollback()

