import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "")
    port: int = int(os.getenv("DB_PORT", "3306"))
    database: str = os.getenv("DB_NAME", "")
    user: str = os.getenv("DB_USER", "")
    password: str = os.getenv("DB_PASSWORD", "")

    @property
    def enabled(self) -> bool:
        return all([self.host, self.database, self.user, self.password])
