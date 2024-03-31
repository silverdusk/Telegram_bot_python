import pytest
import allure
from unittest.mock import patch, MagicMock
from bot.bot import Bot
import logging
import json


@pytest.fixture(scope='session', autouse=True)
def mock_config_file(tmp_path_factory):
    config_file_path = tmp_path_factory.mktemp("config") / "config.json"
    with open(config_file_path, "w") as config_file:
        json.dump({"database": {"db_url": "mocked_database_url"}}, config_file)
    return config_file_path


@allure.feature("Bot")
class TestBot:

    @allure.story("Sending Messages")
    @allure.title("Test Sending Message with Open Error")
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_send_message_open_error(self, mock_open):
        bot = Bot()  # Ensure Bot class reads from config.json
        # Perform your assertions based on the behavior of Bot class when open fails

    @allure.story("Sending Messages")
    @allure.title("Test Sending Message")
    def test_send_message(self, mock_config_file):
        bot = Bot()  # Ensure Bot class reads from config.json
        # Set up any necessary mocks or fixtures for Bot class dependencies
        # Call the method to send a message
        result = bot.send_message("test_chat_id", "Hello, world!")
        # Check if the bot sends the message successfully
        assert result
        # Optionally, assert other behaviors of the Bot class

    @allure.story("Handling Errors")
    @allure.title("Test Handling Error")
    def test_send_message_error(self, mock_config_file):
        bot = Bot()  # Ensure Bot class reads from config.json
        # Set up any necessary mocks or fixtures for Bot class dependencies
        # Set up the mock bot to return an error response when sending a message
        bot.send_message = MagicMock(return_value=False)
        # Call the method to send a message
        result = bot.send_message("test_chat_id", "Hello, world!")
        # Check if the bot handles the error correctly
        assert not result
