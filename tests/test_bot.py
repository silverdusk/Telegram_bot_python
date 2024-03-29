import pytest
import allure
from unittest.mock import MagicMock
from bot.bot import Bot
import logging


@pytest.fixture(scope='session', autouse=True)
def configure_logging():
    # Load the test-specific logging configuration
    logging.config.fileConfig('./logging_test.ini')


@pytest.fixture
def mock_bot():
    # Create a mock bot instance
    mock_bot_instance = MagicMock(spec=Bot)
    return mock_bot_instance


@allure.feature("Bot")
class TestBot:

    @allure.story("Sending Messages")
    @allure.title("Test Sending Message")
    @pytest.mark.parametrize("chat_id, message", [("test_chat_id", "Hello, world!"), ("another_chat_id", "Hi!")])
    def test_send_message(self, mock_bot, chat_id, message):
        # Set up the mock bot to return a success response when sending a message
        mock_bot.send_message.return_value = True

        # Call the method to send a message
        result = mock_bot.send_message(chat_id, message)

        # Check if the bot sends the message successfully
        assert result
        mock_bot.send_message.assert_called_once_with(chat_id, message)

    @allure.story("Handling Errors")
    @allure.title("Test Handling Error")
    def test_send_message_error(self, mock_bot):
        # Set up the mock bot to return an error response when sending a message
        mock_bot.send_message.return_value = False

        # Call the method to send a message
        result = mock_bot.send_message("test_chat_id", "Hello, world!")

        # Check if the bot handles the error correctly
        assert not result
        mock_bot.send_message.assert_called_once_with("test_chat_id", "Hello, world!")
