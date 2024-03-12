import pytest
from unittest.mock import MagicMock
from bot.bot import Bot


@pytest.fixture
def mock_bot():
    # Create a mock bot instance
    mock_bot_instance = MagicMock(spec=Bot)
    return mock_bot_instance


def test_send_message(mock_bot):
    # Set up the mock bot to return a success response when sending a message
    mock_bot.send_message.return_value = True

    # Call the method to send a message
    result = mock_bot.send_message("test_chat_id", "Hello, world!")

    # Check if the bot sends the message successfully
    assert result == True
    mock_bot.send_message.assert_called_once_with("test_chat_id", "Hello, world!")


def test_send_message_error(mock_bot):
    # Set up the mock bot to return an error response when sending a message
    mock_bot.send_message.return_value = False

    # Call the method to send a message
    result = mock_bot.send_message("test_chat_id", "Hello, world!")

    # Check if the bot handles the error correctly
    assert result == False
    mock_bot.send_message.assert_called_once_with("test_chat_id", "Hello, world!")
