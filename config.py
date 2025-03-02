import os

# Flask Secret Key
SECRET_KEY = "Likhi_Nam_0914"  # Change this for better security

# MySQL Database Configuration
MYSQL_CONFIG = {
    "host": "ballast.proxy.rlwy.net",
    "user": "root",
    "password": "nqqXtXTbqtzHwgLBGOBrUtytjOlvIjTI",
    "database": "railway",
    "port": 24246,
}

# Supabase Configuration (if using Supabase for data storage)
SUPABASE_URL = "https://qfqtjwartmcctuvzmhnv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFmcXRqd2FydG1jY3R1dnptaG52Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDA0OTA1NzQsImV4cCI6MjA1NjA2NjU3NH0.vMo4u6ddKeD_AL9ktEgI_or_AzT7s7hakltovL9_FHA"

# Model Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")

# ChromaDB Path
CHROMADB_PATH = os.path.join(BASE_DIR, "chatbot_db")
