from typing import TypeAlias

from discord import Member, Message, User

from ...util import ResponseParameters
from .views import ButtonView

ConversationStore: TypeAlias = dict[int, ResponseParameters]
ViewStore: TypeAlias = dict[Member | User, ButtonView]
ViewMessageStore: TypeAlias = dict[Member | User, Message]
DailyCostStore: TypeAlias = dict[tuple[int, str], float]

__all__ = ["ConversationStore", "ViewStore", "ViewMessageStore", "DailyCostStore"]
