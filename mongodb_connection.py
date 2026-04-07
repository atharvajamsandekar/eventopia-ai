import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://user:pass@cluster.mongodb.net/eventopia?retryWrites=true&w=majority")

def get_mongo_client():
    client = MongoClient(MONGO_URI)
    return client

def get_db():
    client = get_mongo_client()
    return client.get_database() # or get_database("eventopia")
