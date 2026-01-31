# Telegram Bot Project

This project is a Telegram bot built with Python using the Telebot library.

**→ [Deploy and run on a server (manual)](docs/DEPLOY_MANUAL.md)** It allows users to interact with the bot to perform various tasks, such as adding items to a database, retrieving data from the database, and more.

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
- Pytest
- Allure

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

### Setting Up a PostgreSQL Database and Configuring Server with pgAdmin

#### Setting Up a PostgreSQL Database and Table

1. **Install PostgreSQL:**
   - If you haven't already installed PostgreSQL, you can download and install it from the [PostgreSQL website](https://www.postgresql.org/download/).
   - Follow the installation instructions provided for your operating system.

2. **Create a Database:**
   - Once PostgreSQL is installed, open pgAdmin or use the command line to access the PostgreSQL shell (`psql`).
   - In pgAdmin, right-click on "Databases" and select "Create" > "Database".
   - Enter a name for the database and click "Save".
   - Alternatively, in the PostgreSQL shell, run the following SQL command to create a database:
     ```sql
     CREATE DATABASE database_name;
     ```
    Replace `database_name` with the desired name for your database.

3. **Create a Table:**
   - In pgAdmin, navigate to your newly created database, right-click on "Tables", and select "Create" > "Table".
   - Enter the table name and define the table columns along with their data types and constraints.
   - Here's an example SQL query to create the table with the specified fields:
     ```sql
     CREATE TABLE my_table (
         id SERIAL PRIMARY KEY,
         item_name VARCHAR(255),
         item_amount INTEGER,
         item_type VARCHAR(255),
         item_price NUMERIC,
         availability BOOLEAN,
         chat_id BIGINT,
         timestamp TIMESTAMP WITHOUT TIME ZONE
     );
     ```
   - Execute the query to create the table.

4. **Verify Table Creation:**
   - Once the table is created, you should see it listed under the "Tables" section in pgAdmin.
   - You can also verify the table structure by right-clicking on it and selecting "Properties".
5. **Create a Database User:**
- It's recommended to create a separate database user with restricted privileges for your project. This enhances security and isolates the access permissions for different applications.
   - In pgAdmin, in the tree, navigate to "Databases", right-click on "Login/Group Roles", and select "Create" > "Login/Group role".
   - Enter name of the new user and password.
   - Here's an example SQL query to create a new database user:
     ```SQL
     CREATE USER your_username WITH PASSWORD 'your_password';
     ```
   Replace `your_username` with the desired username and `your_password` with the desired password for the user.

6. **Grant Privileges:**
   - After creating the database user, you need to grant necessary privileges to the user on the database you created.
   - Use the following command to grant all privileges on the database to the user:
     ```SQL
     GRANT ALL PRIVILEGES ON DATABASE your_database_name TO your_username;
     ```
   Replace `your_database_name` and `your_username` with the appropriate values.

7. **Grant Permissions:**
- Because the table uses a sequential column (for example, "id SERIAL PRIMARY KEY"), you may need to grant usage on the associated sequence.
   - Use the following command to grant permissions to your user:
     ```SQL
     GRANT USAGE ON SEQUENCE your_database_name_id_seq TO your_username;
     ```
#### Configuring PostgreSQL Server with pgAdmin

1. **Install pgAdmin:**
   - If you haven't already installed pgAdmin, you can download and install it from the [pgAdmin website](https://www.pgadmin.org/download/).
   - Follow the installation instructions provided for your operating system.

2. **Access pgAdmin:**
   - Once pgAdmin is installed, open the application. It usually opens in your default web browser.

3. **Add PostgreSQL Server:**
   - In pgAdmin, click on the "Add New Server" icon or go to the "File" menu and select "Add Server".
   - Enter a name for the server in the "Name" field.
   - In the "Connection" tab:
     - Enter "localhost" or the IP address of your PostgreSQL server in the "Host name/address" field.
     - Enter the port number (default is 5432) in the "Port" field.
     - Enter the username and password you set up during PostgreSQL installation in the "Username" and "Password" fields, respectively.
   - Click "Save" to add the server.

4. **Connect to the Server:**
   - After adding the server, you should see it listed in the pgAdmin interface.
   - Click on the server name to connect to it. You may be prompted to enter the password again.

5. **Explore Databases:**
   - Once connected, you can explore the databases on the server by expanding the server name in the navigation pane.
   - You should see a list of databases, including the one you created for your project.

6. **Manage Databases and Objects:**
   - pgAdmin provides a user-friendly interface for managing databases, tables, and other database objects.
   - You can perform various tasks such as creating tables, executing SQL queries, and managing user permissions directly from pgAdmin.

7. **Verify Configuration:**
   - Verify that you can connect to the PostgreSQL server and access your database from pgAdmin.
   - Ensure that you can perform necessary database operations using pgAdmin, such as creating tables and inserting data.

8. **Verify Setup (optional):**
   - After completing the above steps, you can verify the database setup by connecting to the database using the newly created user credentials:
     ```bash
     psql -U your_username -d your_database_name -h localhost -W
     ```
   You will be prompted to enter the password for the user. If the connection is successful, you will be logged into the PostgreSQL database prompt.

9. **Update Configuration:**
   - In your project's configuration file (`config.json`), update the database connection settings to reflect the database name, username, password, and host (`localhost` if running locally).

10. **Testing Connection:**
    - Before running your application, ensure that it can connect to the PostgreSQL database using the updated configuration. You can test the database connection by attempting to connect from your application code or using a database client.

By following these steps, you can set up a PostgreSQL database for your project and configure your application to interact with it appropriately. Make sure to document any specific requirements or configurations relevant to your project in the README.md file for reference.

## Configuration

- `BOT_TOKEN`: Your Telegram bot token obtained from the BotFather.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: Database connection details.