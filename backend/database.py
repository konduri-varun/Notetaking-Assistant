import motor.motor_asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MONGO_DETAILS = os.environ.get("MONGO_URI")

if not MONGO_DETAILS:
    raise ValueError("Please set the MONGO_URI environment variable in your .env file.")

# Establish an asynchronous connection to the database
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)

# Get a specific database (it will be created if it doesn't exist)
database = client.nylas_transcripts_db

# Get a specific collection to store the transcripts
transcript_collection = database.get_collection("transcripts")
