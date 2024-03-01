# Telegram Bot Project

This project is a Telegram bot built with Python using the Telebot library. It allows users to interact with the bot to perform various tasks, such as adding items to a database, retrieving data from the database, and more.

## Features

- **Item Management**: Users can add, update, and retrieve items stored in a database through simple chat commands.
- **Authorization**: The bot can be configured to only accept commands from authorized users or groups.
- **Flexible Database Queries**: Users can perform flexible database queries, such as retrieving items by name or within a specific time range.
- **Error Handling**: Comprehensive error handling to ensure a smooth user experience.

## Project Structure

The project is organized into the following modules:

1. `bot.py`: Contains main bot logic.
2. `database.py`: Contains logic to interact with the database.
3. `models.py`: Contains the table model.
4. `validators.py`: Contains methods responsible for validating input.


## Requirements

- Python 3.10
- Poetry 
- Postgres
- sqlalchemy 2.0.27

## Installation

1. **Clone the Repository**: 
   Clone this repository to your local machine using the following command:
    git clone <https://github.com/silverdusk/Telegram_bot_python.git>
2. **Navigate to the Project Directory**
3. **Install Python**:
If you haven't already installed Python, you can download it from [official Python website](https://www.python.org/downloads/).
4. **Install PIP (if not already installed)**:
If you haven't already installed PIP, you can download it from [official PIP website](https://pip.pypa.io/en/stable/cli/pip_install/).
5. **Install Poetry (if not already installed)**:
If you haven't already installed Poetry, you can do so using pip:
```Bash
pip install poetry
```
1. **Install Project Dependencies**:
Use Poetry to install the project dependencies specified in the `pyproject.toml` file using command: `poetry install`
2. **Set Up Configuration**:
Set up your configuration settings by creating a `config.json` file in the project directory. You can use the `config.json.example` file from project root directory as a template.
3. **Set Up Logging**:
Configure logging according to your preferences by modifying the `logging.ini` file.
4. **Run the Bot**:
You're all set! Run the bot using the following command:
```Bash
poetry run python bot.py
```

## Configuration

- `BOT_TOKEN`: Your Telegram bot token obtained from the BotFather.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: Database connection details.