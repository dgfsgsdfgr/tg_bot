"""
Сервис планировщика напоминаний с использованием APScheduler
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from typing import Optional
import pytz
import random
from models import Database, Profile
from repository import UserRepository, ProfileRepository


MOTIVATIONAL_MESSAGES = [
    "Не сдавайся! Ты на правильном пути!",
    "Вода - это жизнь! Позаботься о себе!",
    "Каждый глоток приближает тебя к здоровью!",
    "Твоё тело благодарит тебя!",
    "Отличная работа! Продолжай в том же духе!",
    "Здоровье - это самое ценное богатство!",
    "Ты заслуживаешь заботы о себе!",
    "Маленькие шаги ведут к большим результатам!",
    "Вода помогает коже оставаться молодой!",
    "Витамины - залог крепкого иммунитета!",
    "Каждый день ты становишься лучше!",
    "Забота о себе - это не эгоизм, а необходимость!",
]


class ReminderScheduler:
    """Сервис планировщика напоминаний"""

    def __init__(self, bot: Bot, database: Database):
        """
        Инициализация планировщика
        
        Args:
            bot: Экземпляр Telegram бота
            database: Экземпляр базы данных
        """
        self.bot = bot
        self.database = database
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)

    def start(self):
        """Запустить планировщик"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("Планировщик запущен")
            self._restore_all_reminders()

    def shutdown(self):
        """Остановить планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Планировщик остановлен")

    def _restore_all_reminders(self):
        """Восстановить все напоминания после перезапуска бота"""
        session = self.database.get_session()
        try:
            users = UserRepository.get_all_users_with_active_profiles(session)
            count = 0
            for user in users:
                if user.active_profile:
                    removed, added = self._setup_profile_reminders(
                        user.id, 
                        user.active_profile.id,
                        user.timezone
                    )
                    count += added
            print(f"Восстановлено {count} напоминаний для {len(users)} пользователей")
        finally:
            session.close()

    def _get_job_id(self, user_id: str, profile_id: int, time_str: str, reminder_type: str) -> str:
        """
        Получить уникальный ID задачи
        
        Args:
            user_id: ID пользователя
            profile_id: ID профиля
            time_str: Время в формате HH:MM
            reminder_type: Тип напоминания (water/vitamins)
            
        Returns:
            str: Уникальный ID задачи
        """
        return f"reminder_{user_id}_{profile_id}_{time_str}_{reminder_type}"

    def _remove_user_reminders(self, user_id: str) -> int:
        """
        Удалить все напоминания пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            int: Количество удалённых задач
        """
        count = 0
        for job in self.scheduler.get_jobs():
            if job.id.startswith(f"reminder_{user_id}_"):
                job.remove()
                count += 1
        return count

    def _setup_profile_reminders(self, user_id: str, profile_id: int, timezone_str: str) -> tuple[int, int]:
        """
        Настроить напоминания для профиля
        
        Args:
            user_id: ID пользователя
            profile_id: ID профиля
            timezone_str: Часовой пояс
            
        Returns:
            tuple[int, int]: (количество удалённых, количество добавленных)
        """
        removed = self._remove_user_reminders(user_id)
        added = 0

        session = self.database.get_session()
        try:
            profile = ProfileRepository.get(session, profile_id)
            if not profile:
                return removed, added

            reminder_types = profile.reminder_types
            times = profile.time_strings

            if not reminder_types or not times:
                return removed, added

            user_timezone = pytz.timezone(timezone_str)

            for time_str in times:
                hour, minute = map(int, time_str.split(':'))

                for reminder_type in reminder_types:
                    job_id = self._get_job_id(user_id, profile_id, time_str, reminder_type)
                    
                    trigger = CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone=user_timezone
                    )

                    self.scheduler.add_job(
                        self._send_reminder,
                        trigger=trigger,
                        id=job_id,
                        args=[user_id, profile.name, reminder_type],
                        replace_existing=True,
                        misfire_grace_time=300  # 5 минут на случай задержки
                    )
                    added += 1

            print(f"Настроено напоминаний: удалено={removed}, добавлено={added} для пользователя {user_id}")
            return removed, added

        finally:
            session.close()

    async def _send_reminder(self, user_id: str, profile_name: str, reminder_type: str):
        """
        Отправить напоминание пользователю
        
        Args:
            user_id: ID пользователя
            profile_name: Имя профиля
            reminder_type: Тип напоминания (water/vitamins)
        """
        motivation = random.choice(MOTIVATIONAL_MESSAGES)

        if reminder_type == "water":
            text = (
                f"💧 НАПОМИНАНИЕ О ВОДЕ\n\n"
                f"Профиль: {profile_name}\n\n"
                f"✨ {motivation}\n\n"
                f"Время выпить стакан воды! 🥤"
            )
        else:
            text = (
                f"💊 НАПОМИНАНИЕ О ВИТАМИНАХ\n\n"
                f"Профиль: {profile_name}\n\n"
                f"✨ {motivation}\n\n"
                f"Не забудь принять витамины! 🌟"
            )

        try:
            await self.bot.send_message(chat_id=int(user_id), text=text)
            print(f"✓ Напоминание отправлено: user={user_id}, profile={profile_name}, type={reminder_type}")
        except Exception as e:
            print(f"✗ Ошибка отправки напоминания user={user_id}: {e}")

    def setup_user_reminders(self, user_id: str) -> tuple[int, int]:
        """
        Настроить напоминания для активного профиля пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            tuple[int, int]: (количество удалённых, количество добавленных)
        """
        session = self.database.get_session()
        try:
            user = UserRepository.get(session, user_id)
            if not user or not user.active_profile_id:
                removed = self._remove_user_reminders(user_id)
                return removed, 0

            return self._setup_profile_reminders(
                user_id,
                user.active_profile_id,
                user.timezone
            )
        finally:
            session.close()

    def remove_user_reminders(self, user_id: str) -> int:
        """
        Удалить все напоминания пользователя (публичный метод)
        
        Args:
            user_id: ID пользователя
            
        Returns:
            int: Количество удалённых задач
        """
        return self._remove_user_reminders(user_id)

    def get_jobs_count(self, user_id: Optional[str] = None) -> int:
        """
        Получить количество активных задач
        
        Args:
            user_id: ID пользователя (если None, то все задачи)
            
        Returns:
            int: Количество задач
        """
        if user_id:
            return len([j for j in self.scheduler.get_jobs() if j.id.startswith(f"reminder_{user_id}_")])
        return len(self.scheduler.get_jobs())