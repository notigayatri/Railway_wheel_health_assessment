from core.wheel_lifecycle.database import DatabaseManager

db = DatabaseManager()

print("Database created successfully!")

db.close()