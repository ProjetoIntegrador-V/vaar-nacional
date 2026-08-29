
from pymongo import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb://eas:Pass@ac-if7upjx-shard-00-00.wsuqnab.mongodb.net:27017,ac-if7upjx-shard-00-01.wsuqnab.mongodb.net:27017,ac-if7upjx-shard-00-02.wsuqnab.mongodb.net:27017/?ssl=true&replicaSet=atlas-7i234o-shard-0&authSource=admin&appName=Cluster1"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)