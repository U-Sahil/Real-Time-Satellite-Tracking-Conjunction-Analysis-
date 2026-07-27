from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database -----------------------------------------------------
    # SQLite by default (a single file on disk, zero setup — good for
    # development and for a student/demo deployment).
    # For a real deployment, swap this for a Postgres URL, e.g.:
    # postgresql+psycopg2://<user>:<password>@<host>:5432/<db_name>
    database_url: str = "sqlite:///./satellite_platform.db"

   
    jwt_secret_key: str = "CHANGE_ME_DEV_ONLY_NOT_SECURE"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12 hours

    # --- Admin / scheduler ----------------------------------------------
    # Shared secret the Java scheduler sends so random people on the
    # internet can't trigger a TLE refresh. Put the same value in the
    # Java scheduler's config.properties.
    admin_api_key: str = "CHANGE_ME_DEV_ONLY_NOT_SECURE"

    # --- TLE data source --------------------------------------------------
    celestrak_url: str = (
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
    )

    # --- Conjunction screening -------------------------------------------
    conjunction_threshold_km: float = 25.0  # flag pairs closer than this


    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "alerts@satellite-platform.local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
