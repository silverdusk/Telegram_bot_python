from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Item(Base):
    __tablename__ = 'organizer_table'

    id = Column(Integer, primary_key=True)
    item_name = Column(String)
    item_amount = Column(Integer)
    item_type = Column(String)
    item_price = Column(Integer)
    availability = Column(Integer)
    timestamp = Column(DateTime)
    chat_id = Column(Integer)

    def __repr__(self):
        return f"<Item(id={self.id}, item_name={self.item_name}, item_amount={self.item_amount})>"
