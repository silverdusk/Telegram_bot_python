-- Indexes for organizer_table (items) to speed up common queries.
-- Run after tables exist (e.g. after create_tables or Create_table_script).
-- get_items(chat_id=..., limit) + order by timestamp:
CREATE INDEX IF NOT EXISTS idx_organizer_chat_timestamp
  ON organizer_table (chat_id, timestamp DESC);

-- get_items(chat_id=..., item_name=...), delete_by_name_and_chat, update_availability:
CREATE INDEX IF NOT EXISTS idx_organizer_chat_name
  ON organizer_table (chat_id, item_name);

-- Filter by creator (get_items created_by_user_id, permission checks):
CREATE INDEX IF NOT EXISTS idx_organizer_created_by_user_id
  ON organizer_table (created_by_user_id)
  WHERE created_by_user_id IS NOT NULL;

-- users.telegram_user_id and roles.name already have unique constraints (indexes).
-- No extra indexes needed for users/roles for current query patterns.
