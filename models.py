"""
Модели базы данных для Telegram-бота напоминаний
"""

from sqlalchemy import create_engine, Column, String, Integer, Boolean, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from typing import List

Base = declarative_base()

# Таблица связи многие-ко-многим для времени напоминаний
profile_times = Table(
    'profile_times',
    Base.metadata,
    Column('profile_id', Integer, ForeignKey('profiles.id', ondelete='CASCADE'), primary_key=True),
    Column('time_id', Integer, ForeignKey('reminder_times.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = Column(String, primary_key=True)  # Telegram user_id как строка
    timezone = Column(String, default='Europe/Moscow', nullable=False)
    active_profile_id = Column(Integer, ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True)

    # Relationships
    profiles = relationship('Profile', back_populates='user', foreign_keys='Profile.user_id',
                          cascade='all, delete-orphan')
    active_profile = relationship('Profile', foreign_keys=[active_profile_id], post_update=True)

    def __repr__(self):
        return f"<User(id={self.id}, timezone={self.timezone})>"


class Profile(Base):
    """Модель профиля напоминаний"""
    __tablename__ = 'profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String, nullable=False)
    reminder_water = Column(Boolean, default=False)
    reminder_vitamins = Column(Boolean, default=False)

    # Relationships
    user = relationship('User', back_populates='profiles', foreign_keys=[user_id])
    times = relationship('ReminderTime', secondary=profile_times, back_populates='profiles',
                        cascade='all, delete')

    def __repr__(self):
        return f"<Profile(id={self.id}, name={self.name}, user_id={self.user_id})>"

    @property
    def reminder_types(self) -> List[str]:
        """Получить список типов напоминаний"""
        types = []
        if self.reminder_water:
            types.append('water')
        if self.reminder_vitamins:
            types.append('vitamins')
        return types

    @property
    def time_strings(self) -> List[str]:
        """Получить список времён в формате HH:MM"""
        return sorted([t.time_str for t in self.times])


class ReminderTime(Base):
    """Модель времени напоминания"""
    __tablename__ = 'reminder_times'

    id = Column(Integer, primary_key=True, autoincrement=True)
    time_str = Column(String, unique=True, nullable=False)  # Формат "HH:MM"

    # Relationships
    profiles = relationship('Profile', secondary=profile_times, back_populates='times')

    def __repr__(self):
        return f"<ReminderTime(id={self.id}, time={self.time_str})>"


class Database:
    """Класс для работы с базой данных"""

    def __init__(self, db_url: str = 'sqlite:///bot_data.db'):
        """
        Инициализация базы данных
        
        Args:
            db_url: URL подключения к базе данных
        """
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def get_session(self):
        """Получить новую сессию базы данных"""
        return self.SessionLocal()

    def close(self):
        """Закрыть соединение с базой данных"""
        self.engine.dispose()