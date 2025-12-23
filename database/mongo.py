import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI in .env")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["mydb"]
admins = db["admins"]
users = db["users"]
posts = db["posts"]
comments = db["comments"]
post_likes = db["post_likes"]
locations = db["locations"]
gallery_collection = db["gallery"]

def init_indexes() -> None:
    # Fail fast if cannot connect
    client.admin.command("ping")

    users.create_index([("email", 1)], unique=True)
    posts.create_index([("createdAt", -1)])
    posts.create_index([("authorId", 1), ("createdAt", -1)])
    post_likes.create_index([("postId", 1), ("userId", 1)], unique=True)
    post_likes.create_index([("postId", 1), ("createdAt", -1)])
    comments.create_index([("postId", 1), ("createdAt", -1)])