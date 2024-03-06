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

### Setting Up a PostgreSQL Database

1. **Install PostgreSQL:**
   - If PostgreSQL is not already installed on your system, follow the instructions provided on the [PostgreSQL official website](https://www.postgresql.org/download/) to download and install PostgreSQL for your operating system.

2. **Create a Database:**
   - Once PostgreSQL is installed, open a terminal or command prompt and access the PostgreSQL command-line interface by running `psql` (on Unix-based systems) or accessing the `psql` command from the PostgreSQL installation directory.
   - Use the following command to create a new database for your project:
     ```sql
     CREATE DATABASE your_database_name;
     ```
   Replace `your_database_name` with the desired name for your database.

3. **Create a Database User:**
   - It's recommended to create a separate database user with restricted privileges for your project. This enhances security and isolates the access permissions for different applications.
   - Use the following command to create a new database user:
     ```sql
     CREATE USER your_username WITH PASSWORD 'your_password';
     ```
   Replace `your_username` with the desired username and `your_password` with the desired password for the user.

4. **Grant Privileges:**
   - After creating the database user, you need to grant necessary privileges to the user on the database you created.
   - Use the following command to grant all privileges on the database to the user:
     ```sql
     GRANT ALL PRIVILEGES ON DATABASE your_database_name TO your_username;
     ```
   Replace `your_database_name` and `your_username` with the appropriate values.

5. **Verify Setup:**
   - After completing the above steps, you can verify the database setup by connecting to the database using the newly created user credentials:
     ```bash
     psql -U your_username -d your_database_name -h localhost -W
     ```
   You will be prompted to enter the password for the user. If the connection is successful, you will be logged into the PostgreSQL database prompt.

6. **Update Configuration:**
   - In your project's configuration file (`config.json` or similar), update the database connection settings to reflect the database name, username, password, and host (`localhost` if running locally).

7. **Testing Connection:**
   - Before running your application, ensure that it can connect to the PostgreSQL database using the updated configuration. You can test the database connection by attempting to connect from your application code or using a database client.

By following these steps, you can set up a PostgreSQL database for your project and configure your application to interact with it appropriately. Make sure to document any specific requirements or configurations relevant to your project in the README.md file for reference.

## Configuration

- `BOT_TOKEN`: Your Telegram bot token obtained from the BotFather.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: Database connection details.