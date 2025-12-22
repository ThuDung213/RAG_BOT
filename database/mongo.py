from pymongo import MongoClient

client = MongoClient("mongodb+srv://dungttt21it_db_user:myproject123@cluster0.wjbca0f.mongodb.net/?appName=Cluster0")
db = client["mydb"]     
admins = db["admins"] 
locations = db["locations"]

client.admin.command("ping")
print("OK")
