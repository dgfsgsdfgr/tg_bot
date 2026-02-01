"""
Repository - слой доступа к данным
"""

from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from models import User, Profile, ReminderTime


class UserRepository:
    """Репозиторий для работы с пользователями"""

    @staticmethod
    def get_or_create(session: Session, user_id: str) -> User:
        """
        Получить или создать пользователя
        
        Args:
            session: Сессия базы данных
            user_id: Telegram ID пользователя
            
        Returns:
            User: Объект пользователя
        """
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, timezone='Europe/Moscow')
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def get(session: Session, user_id: str) -> Optional[User]:
        """Получить пользователя по ID"""
        return session.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_timezone(session: Session, user_id: str, timezone: str) -> User:
        """Обновить часовой пояс пользователя"""
        user = UserRepository.get_or_create(session, user_id)
        user.timezone = timezone
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def set_active_profile(session: Session, user_id: str, profile_id: Optional[int]) -> User:
        """Установить активный профиль"""
        user = UserRepository.get_or_create(session, user_id)
        user.active_profile_id = profile_id
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def get_all_users_with_active_profiles(session: Session) -> List[User]:
        """Получить всех пользователей с активными профилями"""
        return session.query(User).filter(User.active_profile_id.isnot(None)).all()


class ProfileRepository:
    """Репозиторий для работы с профилями"""

    @staticmethod
    def create(session: Session, user_id: str, name: str) -> Profile:
        """Создать новый профиль"""
        profile = Profile(user_id=user_id, name=name)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile

    @staticmethod
    def get(session: Session, profile_id: int) -> Optional[Profile]:
        """Получить профиль по ID"""
        return session.query(Profile).filter(Profile.id == profile_id).first()

    @staticmethod
    def get_by_user(session: Session, user_id: str) -> List[Profile]:
        """Получить все профили пользователя"""
        return session.query(Profile).filter(Profile.user_id == user_id).all()

    @staticmethod
    def get_by_name(session: Session, user_id: str, name: str) -> Optional[Profile]:
        """Получить профиль по имени"""
        return session.query(Profile).filter(
            Profile.user_id == user_id,
            Profile.name == name
        ).first()

    @staticmethod
    def delete(session: Session, profile_id: int) -> bool:
        """Удалить профиль"""
        profile = ProfileRepository.get(session, profile_id)
        if profile:
            session.delete(profile)
            session.commit()
            return True
        return False

    @staticmethod
    def update_reminder_types(session: Session, profile_id: int, 
                            water: bool, vitamins: bool) -> Profile:
        """Обновить типы напоминаний"""
        profile = ProfileRepository.get(session, profile_id)
        if profile:
            profile.reminder_water = water
            profile.reminder_vitamins = vitamins
            session.commit()
            session.refresh(profile)
        return profile

    @staticmethod
    def toggle_water(session: Session, profile_id: int) -> Profile:
        """Переключить напоминание о воде"""
        profile = ProfileRepository.get(session, profile_id)
        if profile:
            profile.reminder_water = not profile.reminder_water
            session.commit()
            session.refresh(profile)
        return profile

    @staticmethod
    def toggle_vitamins(session: Session, profile_id: int) -> Profile:
        """Переключить напоминание о витаминах"""
        profile = ProfileRepository.get(session, profile_id)
        if profile:
            profile.reminder_vitamins = not profile.reminder_vitamins
            session.commit()
            session.refresh(profile)
        return profile


class ReminderTimeRepository:
    """Репозиторий для работы со временем напоминаний"""

    @staticmethod
    def get_or_create(session: Session, time_str: str) -> ReminderTime:
        """Получить или создать время напоминания"""
        reminder_time = session.query(ReminderTime).filter(
            ReminderTime.time_str == time_str
        ).first()
        if not reminder_time:
            reminder_time = ReminderTime(time_str=time_str)
            session.add(reminder_time)
            session.commit()
            session.refresh(reminder_time)
        return reminder_time

    @staticmethod
    def add_to_profile(session: Session, profile_id: int, time_str: str) -> bool:
        """Добавить время к профилю"""
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            return False

        reminder_time = ReminderTimeRepository.get_or_create(session, time_str)
        
        if reminder_time not in profile.times:
            profile.times.append(reminder_time)
            session.commit()
        return True

    @staticmethod
    def remove_from_profile(session: Session, profile_id: int, time_str: str) -> bool:
        """Удалить время из профиля"""
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            return False

        reminder_time = session.query(ReminderTime).filter(
            ReminderTime.time_str == time_str
        ).first()
        
        if reminder_time and reminder_time in profile.times:
            profile.times.remove(reminder_time)
            session.commit()
            return True
        return False

    @staticmethod
    def clear_profile_times(session: Session, profile_id: int) -> bool:
        """Очистить все времена профиля"""
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            return False

        profile.times.clear()
        session.commit()
        return True

    @staticmethod
    def toggle_time(session: Session, profile_id: int, time_str: str) -> bool:
        """Переключить время (добавить/удалить)"""
        profile = ProfileRepository.get(session, profile_id)
        if not profile:
            return False

        reminder_time = session.query(ReminderTime).filter(
            ReminderTime.time_str == time_str
        ).first()

        if reminder_time and reminder_time in profile.times:
            profile.times.remove(reminder_time)
        else:
            if not reminder_time:
                reminder_time = ReminderTime(time_str=time_str)
                session.add(reminder_time)
            profile.times.append(reminder_time)
        
        session.commit()
        return True