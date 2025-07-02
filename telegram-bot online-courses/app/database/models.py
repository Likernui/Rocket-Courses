from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession
from dotenv import load_dotenv
from os import getenv
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON

load_dotenv()
DB_URL = getenv('DB_URL')

Base = declarative_base(cls=AsyncAttrs)

engine = create_async_engine(url=DB_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(200))

    # Отношение к курсам (один ко многим)
    courses = relationship("Course", back_populates="category", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))  # Новое поле
    registered_at = Column(DateTime, default=datetime.utcnow)
    balance = Column(Integer, default=0)
    purchased_courses = Column(JSON, default=list)

    purchases = relationship("Purchase", back_populates="user")


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(500))
    price = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    link = Column(String(200), nullable=False, unique=True)
    category = relationship("Category", back_populates="courses")
    purchases = relationship("Purchase", back_populates="course")


class Purchase(Base):
    __tablename__ = 'purchases'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    purchase_date = Column(DateTime, default=datetime.utcnow)
    amount = Column(Integer)

    # Отношения к пользователю и курсу (многие к одному)
    user = relationship("User", back_populates="purchases")
    course = relationship("Course", back_populates="purchases")


class PendingPayment(Base):
    __tablename__ = "pending_payments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"))  # Изменено с BigInteger на Integer
    course_id = Column(Integer, ForeignKey("courses.id"))
    payment_id = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending")
    user = relationship("User", back_populates="pending_payments")
    course = relationship("Course")


User.pending_payments = relationship("PendingPayment", back_populates="user")


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)