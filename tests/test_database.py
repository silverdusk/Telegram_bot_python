import pytest
from unittest.mock import MagicMock
import allure
from database.database import Database


@pytest.fixture
def mock_database():
    # Create a mock database instance
    mock_db_instance = MagicMock(spec=Database)
    return mock_db_instance


@allure.feature("Database Operations")
class TestDatabase:

    @allure.story("Inserting Items")
    def test_insert_item_success(self, mock_database):
        # Set up the mock database to return a success response when inserting an item
        mock_database.insert_item.return_value = True

        # Call the method to insert an item into the database
        result = mock_database.insert_item("test_item")

        # Check if the item is inserted successfully
        assert result
        mock_database.insert_item.assert_called_once_with("test_item")
        allure.attach("Inserted Item", "test_item", allure.attachment_type.TEXT)

    @allure.story("Inserting Items")
    def test_insert_item_error(self, mock_database):
        # Set up the mock database to return an error response when inserting an item
        mock_database.insert_item.return_value = False

        # Call the method to insert an item into the database
        result = mock_database.insert_item("test_item")

        # Check if the database handles the error correctly
        assert not result
        mock_database.insert_item.assert_called_once_with("test_item")
        allure.attach("Error Inserting Item", "test_item", allure.attachment_type.TEXT)
