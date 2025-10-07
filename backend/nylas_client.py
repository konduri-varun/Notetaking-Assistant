import os
from nylas import Client
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
NYLAS_API_KEY = os.environ.get("NYLAS_API_KEY")
NYLAS_GRANT_ID = os.environ.get("NYLAS_GRANT_ID")

if not NYLAS_API_KEY or not NYLAS_GRANT_ID:
    raise ValueError(
        "Please set the NYLAS_API_KEY and NYLAS_GRANT_ID environment variables."
    )

# --- Initialize the Nylas Client ---
try:
    client = Client(api_key=NYLAS_API_KEY)
except Exception as e:
    print(f"Error initializing Nylas client: {e}")
    # Handle the error appropriately
    client = None