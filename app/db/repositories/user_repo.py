"""User repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_or_create_default(self, display_name: str = "default") -> User:
        stmt = select(User).where(User.display_name == display_name).limit(1)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user
        return await self.create(User(display_name=display_name, is_active=True))
