import pytest
from unittest.mock import MagicMock
from bot.bot import Bot


@pytest.fixture
def bot():
    # Set up your bot instance
    return Bot()


def test_handle_message(bot):
    # Arrange
    message = MagicMock()
    message.text = "Hello Bot"

    # Act
    bot.handle_message(message)

    # Assert
    assert bot.last_message == "Received message: Hello Bot"


def test_send_message(bot):
    # Arrange
    chat_id = 123456789
    text = "Test message"

    # Act
    bot.send_message(chat_id, text)

    # Assert
    assert bot.sent_messages[chat_id] == text


def test_handle_callback_query(bot):
    # Arrange
    query = MagicMock()
    query.data = "callback_data"

    # Act
    bot.handle_callback_query(query)

    # Assert
    assert bot.last_callback_data == "callback_data"
