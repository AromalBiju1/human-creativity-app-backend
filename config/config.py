from dotenv import load_dotenv
import os
load_dotenv()


private_key = os.getenv("PRIVATE_KEY")
public_key = os.getenv("PUBLIC_KEY")
database_url = os.getenv("DATABASE_URL")

