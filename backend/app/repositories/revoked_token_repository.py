from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.revoked_token import RevokedToken


class RevokedTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_jti(self, jti: str) -> RevokedToken | None:
        """Повертає відкликаний токен за його JTI."""
        statement = select(RevokedToken).where(
            RevokedToken.jti == jti
        )

        return self.db.scalar(statement)

    def is_revoked(self, jti: str) -> bool:
        """Перевіряє, чи відкликано JWT."""
        return self.get_by_jti(jti) is not None

    def create(
        self,
        jti: str,
        expires_at: datetime
    ) -> RevokedToken:
        """Додає JWT до списку відкликаних токенів."""
        revoked_token = RevokedToken(
            jti=jti,
            expires_at=expires_at
        )

        self.db.add(revoked_token)
        self.db.flush()

        return revoked_token
