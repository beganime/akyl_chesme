# Собираем все модели в одном месте для удобного импорта
from .user import User
from .bot import BotConfig
from .device import DeviceSession
from .chat import Chat, ChatMember
from .message import Message, Attachment
from .contact import Contact
from .user_settings import UserSettings