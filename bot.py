import os
import datetime
import pytz
import telebot
import psycopg2
from psycopg2 import OperationalError
import re
import logging
import json
import database
import validators


# Load logging configuration from logging.ini
logging.config.fileConfig('logging.ini')
logging.info("Starting bot successfully at: " + str(datetime.datetime.utcnow()) + " UTC")

with open('config.json', 'r') as file:
    config = json.load(file)

# BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(config['bot_token'])
AUTHORIZED_IDS = config['authorized_ids']
ALLOWED_TYPES = config['allowed_types']


class UserInput:
    # this class stores user input
    def __init__(self, item_name='', item_amount=0, item_type='spare part', item_price=0.0, availability=False):
        self.item_name = item_name
        self.item_amount = item_amount
        self.item_type = item_type
        self.item_price = item_price
        self.availability = availability


demo_message = UserInput(item_name='My Item',
                         item_amount=1,
                         item_type='spare part',
                         item_price=0.01,
                         availability=True)


def send_demo_message(message):
    request = demo_message
    ok_request(message, request)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    logging.info("Received '/start' command")
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.add(telebot.types.KeyboardButton('Get'))
    keyboard.add(telebot.types.KeyboardButton('Add'))
    keyboard.add(telebot.types.KeyboardButton('Admin'))
    keyboard.add(telebot.types.KeyboardButton('Send test message'))
    keyboard.add(telebot.types.KeyboardButton('Change availability status'))
    bot.send_message(message.chat.id,
                     "Hi! :)\nI'm organizer bot. I will help you to add your items.",
                     reply_markup=keyboard)


@bot.message_handler(commands=['menu'])
def menu(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton('Get', callback_data='Get'))
    keyboard.add(telebot.types.InlineKeyboardButton('Add', callback_data='Add'))
    keyboard.add(telebot.types.InlineKeyboardButton('Admin', callback_data='Admin'))
    keyboard.add(telebot.types.InlineKeyboardButton('Change availability status', callback_data='availability_status'))
    keyboard.add(telebot.types.InlineKeyboardButton('Send test message', callback_data='Send test message'))
    keyboard.add(telebot.types.InlineKeyboardButton('Stop', callback_data='stop_bot'))
    bot.send_message(message.chat.id, 'What you want to do?', reply_markup=keyboard)


@bot.message_handler(regexp='^admin$')
def admin(message):
    bug(message)


@bot.message_handler(regexp='^get$')
def get(message):
    get_items_from_database(message)


@bot.message_handler(regexp='^add$')
def add(message):
    add_item(message)


@bot.message_handler(regexp='^Send test message$')
def test(message):
    send_demo_message(message)


@bot.message_handler(regexp='^Change availability status$')
def availability_status(message):
    update_availability_status(message)


@bot.message_handler(regexp='^stop_bot$')
def stop(message):
    stop_bot(message)


@bot.callback_query_handler(func=lambda c: True)
def submenus(c):
    if c.data == 'Add':
        add_item(c.message)
    elif c.data == 'Get':
        bug(c.message)
    elif c.data == 'Admin':
        bug(c.message)
    elif c.data == 'Send test message':
        send_demo_message(c.message)


@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.reply_to(message, message.text)


def bug(message):
    bot.send_photo(chat_id=message.chat.id,
                   photo='https://cdn-icons-png.flaticon.com/512/249/249389.png',
                   caption='We\'re working on it!',
                   protect_content=True)


def add_item(message):
    if validators.check_working_hours():
        msg = bot.send_message(message.chat.id, 'Please provide name of item:', reply_markup=telebot.types.ForceReply())
        order = UserInput()
        bot.register_next_step_handler(msg, check_item_name, order)
    else:
        bot.send_message(message.chat.id, 'You are trying to send request outside of working hours - please try '
                                          'again later.')


def check_item_name(message, order):
    # message.text - value of user input
    # send request to check availability of item
    # for now it will be always true
    if validators.text_input_validator(message):
        order.item_name = message.text
        msg = bot.send_message(message.chat.id, 'Please provide amount of items:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_amount, order)
    else:
        msg = bot.send_message(message.chat.id,
                               f'{message.text} is invalid.\n'
                               f'Please provide item name:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_name, order)


def check_availability_name(message):
    result = validators.text_input_validator(message)
    if result:
        name = message.text.upper()
        print('name', name)
        msg = bot.send_message(message.chat.id, 'Please provide availability status of item YES/NO :',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_availability_item, name)


def check_availability_item(message, item):
    if message.text.upper() == "YES":
        bot.send_message(message.chat.id,
                         f'Update availability status.\n'
                         f'Item {item}. \n'
                         f'Availability - not available')
        # Establish connection to Postgres database
        conn = database.create_database_connection()
        if conn is not None:
            try:
                # Update availability status in Postgres database
                database.update_availability_in_database(conn, item, True)
            finally:
                # Close the connection to the Postgres database
                if conn:
                    conn.close()
    elif message.text.upper() == "NO":
        bot.send_message(message.chat.id,
                         f'Update availability status.\n'
                         f'Item {item}. \n'
                         f'Availability - not available')
        # Establish connection to Postgres database
        conn = database.create_database_connection()
        if conn is not None:
            try:
                # Update availability status in Postgres database
                database.update_availability_in_database(conn, item, False)
            finally:
                # Close the connection to the Postgres database
                if conn:
                    conn.close()
    else:
        msg = bot.send_message(message.chat.id,
                               f'Incorrect value, must be YES/NO')
        bot.register_next_step_handler(msg, check_availability_item, item)


def check_item_amount(message, request):
    # message.text - value of user input
    if validators.is_int(message.text):
        request.item_amount = message.text
        msg = bot.send_message(message.chat.id, 'Please provide item type:', reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_type, request)
    else:
        msg = bot.send_message(message.chat.id,
                               f'{message.text} is invalid.\n'
                               f'Please provide item amount:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_amount, request)


def check_item_type(message, request):
    if message.text.lower() not in [x.lower() for x in ALLOWED_TYPES]:
        msg = bot.send_message(message.chat.id,
                               f'{message.text} is not allowed item type.'
                               f' Allowed Items Types are: {" or ".join(ALLOWED_TYPES)}.\nPlease provide item type:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_type, request)
    else:
        request.item_type = message.text.lower()
        if message.text.lower() == 'spare part':
            msg = bot.send_message(message.chat.id, 'Please provide item price value:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, check_item_price_value, request)
        else:
            msg = bot.send_message(message.chat.id, 'Please provide item price value:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, check_item_price_value, request)


def check_item_price_value(message, request):
    if validators.is_float(message.text):
        request.item_price = message.text
        msg = bot.send_message(message.chat.id,
                               f'price {message.text} is correct.\n'
                               f'Please provide availability status:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_availability_status, request)
    else:
        msg = bot.send_message(message.chat.id,
                               f'{message.text} is invalid.\n'
                               f'Please provide item price value:',
                               reply_markup=telebot.types.ForceReply())
        bot.register_next_step_handler(msg, check_item_price_value, request)


def check_availability_status(message, request):
    if message.text == 'yes':
        request.availability = True
        validate_request(message, request)
    elif message.text == 'no':
        request.availability = False
        validate_request(message, request)
    elif message.text:
        msg = bot.send_message(message.chat.id,
                               f'Incorrect value, must be yes/no')
        bot.register_next_step_handler(msg, check_availability_status, request)


def validate_request(message, request):
    keyboard = telebot.types.ReplyKeyboardMarkup(is_persistent=True)
    keyboard.add(telebot.types.KeyboardButton('Request is correct'))
    keyboard.add(telebot.types.KeyboardButton('No, I want to edit my request'))
    text = f'Please check values:{os.linesep}' \
           f'Item name: {request.item_name}, {os.linesep}' \
           f'Items amount: {request.item_amount}, {os.linesep}' \
           f'Item type: {request.item_type}, {os.linesep}'
    if request.item_type == 'spare part':
        text.join(f'Item price: {request.item_price}, {os.linesep}')
        text.join(f'Availability: {request.availability}, {os.linesep}')
    text += f'Is request correct?'
    msg = bot.send_message(message.chat.id, text, reply_markup=keyboard)

    bot.register_next_step_handler(msg, request_decision_handler, request)


def request_decision_handler(message, request):
    if message.text == 'Request is correct':
        ok_request(message, request)
    elif message.text == 'No, I want to edit my request':
        edit_request(message, request)
    else:
        msg = bot.send_message(message.chat.id, f'Wrong value provided. {os.linesep}'
                                                f'Try again.')
        bot.register_next_step_handler(msg, request_decision_handler, request)


def ok_request(message, request):
    # Create a session using the sessionmaker
    session = database.create_database_session()
    if session is not None:
        try:
            # Insert data into Postgres database
            if database.insert_item(session, message, request):
                # Construct the text message to send
                text = f'Request is placed for processing:{os.linesep}' \
                       f'Item name: {request.item_name}, {os.linesep}' \
                       f'Amount of items: {request.item_amount}, {os.linesep}' \
                       f'Item type: {request.item_type}, {os.linesep}'
                if request.item_type == 'spare part':
                    text += f'Item price: {request.item_price}, {os.linesep}'
                    text += f'Availability: {request.availability}, {os.linesep}'
                # Send the text message using the bot
                bot.send_message(message.chat.id, text)
            else:
                bot.send_message(message.chat.id, "Failed to process the request. Please try again later.")
        except Exception as e:
            bot.send_message(message.chat.id, f"An error occurred: {e}")
            logging.error(f"An error occurred: {e}")
        finally:
            # Close the connection to the Postgres database
            if session:
                session.close()


def edit_request(message, request):
    keyboard = telebot.types.ReplyKeyboardMarkup()
    keyboard.add(telebot.types.KeyboardButton('Item name'))
    keyboard.add(telebot.types.KeyboardButton('Items amount'))
    keyboard.add(telebot.types.KeyboardButton('Item type'))
    if request.item_type == 'spare part':
        keyboard.add(telebot.types.KeyboardButton('Item price'))
        keyboard.add(telebot.types.KeyboardButton('Availability'))
    msg = bot.send_message(message.chat.id, 'What do you want to edit?', reply_markup=keyboard)
    bot.register_next_step_handler(msg, edit_request_values, request)


def edit_request_values(message, request):
    if message.text == 'Item name':
        edit_type = 'name'
    elif message.text == 'Amount of items':
        edit_type = 'amount'
    elif message.text == 'Item type':
        edit_type = 'type'
    elif message.text == 'Item price':
        edit_type = 'item_price'
    elif message.text == 'Availability':
        edit_type = 'availability'
    else:
        edit_type = 'unknown'

    edit_items_value(message, request, edit_type)


def edit_items_value(message, request, items_type):
    if items_type == 'name':
        msg = bot.send_message(message.chat.id, 'Please provide new Item name:',
                               reply_markup=telebot.types.ForceReply())
    elif items_type == 'amount':
        msg = bot.send_message(message.chat.id, 'Please provide new amount:',
                               reply_markup=telebot.types.ForceReply())
    elif items_type == 'type':
        msg = bot.send_message(message.chat.id, 'Please provide new Item type:',
                               reply_markup=telebot.types.ForceReply())
    elif items_type == 'item_price':
        msg = bot.send_message(message.chat.id, 'Please provide new item price:',
                               reply_markup=telebot.types.ForceReply())
    elif items_type == 'availability':
        msg = bot.send_message(message.chat.id, 'Please provide new availability status:',
                               reply_markup=telebot.types.ForceReply())
    else:
        msg = bot.send_message(message.chat.id, f'Seems you provide wrong value... {os.linesep}'
                                                f'Try again.{os.linesep}'
                                                f'What do you want to edit?')

        bot.register_next_step_handler(msg, edit_request_values, request)
        return
    bot.register_next_step_handler(msg, update_items_value, request, items_type)


def update_items_value(message, request, items_type):
    if items_type == 'name':
        result = validators.text_input_validator(message)
        if result:
            request.item_name = message.text.upper()
        else:
            msg = bot.send_message(message.chat.id,
                                   f'{message.text} is invalid.\n'
                                   f'Please provide item name:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, update_items_value, request, 'name')
    elif items_type == 'amount':
        if validators.is_int(message.text):
            request.item_amount = message.text
        else:
            msg = bot.send_message(message.chat.id,
                                   f'{message.text} is invalid.\n'
                                   f'Please provide amount of items:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, update_items_value, request, 'amount')
    elif items_type == 'type':
        if message.text.lower() not in [x.lower() for x in ALLOWED_TYPES]:
            msg = bot.send_message(message.chat.id,
                                   f'{message.text} is not allowed Item type.'
                                   f' Allowed Item Types are: {" or ".join(ALLOWED_TYPES)}.\nPlease provide '
                                   'Item type:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, edit_items_value, request, 'type')
        else:
            request.item_type = message.text.lower()
    elif items_type == 'item_price':
        if validators.is_int(message.text):
            request.item_price = message.text
        else:
            msg = bot.send_message(message.chat.id,
                                   f'{message.text} is invalid.\n'
                                   f'Please provide item price value:',
                                   reply_markup=telebot.types.ForceReply())
            bot.register_next_step_handler(msg, update_items_value, request, 'limit_price')
    elif items_type == "spare part":
        if message.text == "yes":
            request.availability = True
        if message.text == "no":
            request.availability = False
    else:
        msg = bot.send_message(message.chat.id, f'Wrong value provided. {os.linesep}Try again')
        bot.register_next_step_handler(msg, edit_request, request)
        return

    validate_request(message, request)


def update_availability_status(message):
    msg = bot.send_message(message.chat.id, 'Please provide availability '
                                            'status:', reply_markup=telebot.types.ForceReply())
    bot.register_next_step_handler(msg, check_availability_name)


# Define a signal handler to stop the bot gracefully
@bot.message_handler(commands=['stop'])
def stop_bot(message):
    if message.chat.id not in AUTHORIZED_IDS:
        bot.send_message(message.chat.id, f"Your ID ({message.chat.id}) is not authorized to stop bot")
        logging.warning(f"Unauthorized attempt to stop bot from chat {message.chat.id}")
        return
    logging.info("Stopping bot...")
    print("Stopping bot...")
    bot.reply_to(message, "Stopping bot...")

    bot.stop_polling()

    logging.info("Bot stopped at: " + str(datetime.datetime.utcnow()) + " UTC")
    print("Bot stopped.")
    exit(0)


def get_items_from_database(message):
    session = database.create_database_session()
    try:
        start_date = datetime.datetime(2024, 1, 1)
        end_date = datetime.datetime(2024, 2, 1)
        items = database.get_items(session, item_name='test', start_date=start_date, end_date=end_date)
        if items:
            item_info = "\n".join([f"Item: {item.item_name}, Amount: {item.item_amount}" for item in items])
            bot.send_message(message.chat.id, f"Items in the database:\n{item_info}")
        else:
            bot.send_message(message.chat.id, "The item not found in the database.")
    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")
        logging.error(f"Failed get items from database with error: {e}")
    finally:
        if session:
            session.close()


# Register the signal handler for SIGINT and SIGTERM
# signal.signal(signal.SIGINT, stop_bot)
# signal.signal(signal.SIGTERM, stop_bot)

# Start the bot's polling loop
bot.polling()
# bot.infinity_polling()
