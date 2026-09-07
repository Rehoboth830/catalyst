import os
from dotenv import load_dotenv

load_dotenv()

required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "DATABASE_URL"]

for var in required_vars:
    value = os.environ.get(var)
    if value:
        masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"{var}: LOADED ({masked})")
    else:
        print(f"{var}: MISSING")
