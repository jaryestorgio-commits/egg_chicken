from datetime import datetime, timezone
from extensions import db


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"

    jti = db.Column(db.String(36), primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))