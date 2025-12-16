from dotenv import load_dotenv
import os
from pathlib import Path
load_dotenv()
private_key = Path(os.environ["JWT_PRIVATE_KEY_PATH"])
public_key = Path(os.environ["JWT_PUBLIC_KEY_PATH"])
database_url = os.getenv("DATABASE_URL")

