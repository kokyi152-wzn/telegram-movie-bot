from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DB_NAME
from datetime import datetime


class Database:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]
        await self.db.posts.create_index("post_id", unique=True)
        await self.db.users.create_index("_id")
        await self.db.schedules.create_index("send_at")
        await self.db.batch_links.create_index("batch_id", unique=True)

    async def close(self):
        if self.client:
            self.client.close()

    async def add_user(self, user_id, username, first_name):
        existing = await self.db.users.find_one({"_id": user_id})
        if not existing:
            await self.db.users.insert_one({
                "_id": user_id,
                "username": username or "",
                "first_name": first_name or "",
                "total_downloads": 0,
                "created_at": datetime.utcnow(),
            })
            return True
        return False

    async def increment_user_downloads(self, user_id):
        await self.db.users.update_one(
            {"_id": user_id}, {"$inc": {"total_downloads": 1}}
        )

    async def count_users(self):
        return await self.db.users.count_documents({})

    async def save_post(self, post_id, title, script_text, telegraph_url,
                        poster_file_ids, movie_file_id, movie_file_name,
                        channel_message_id=None, genres="", year="", rating=""):
        return await self.db.posts.insert_one({
            "post_id": post_id,
            "title": title,
            "script_text": script_text,
            "telegraph_url": telegraph_url,
            "poster_file_ids": poster_file_ids,
            "movie_file_id": movie_file_id,
            "movie_file_name": movie_file_name,
            "channel_message_id": channel_message_id,
            "genres": genres,
            "year": year,
            "rating": rating,
            "created_at": datetime.utcnow(),
        })

    async def get_post(self, post_id):
        return await self.db.posts.find_one({"post_id": post_id})

    async def get_all_posts(self, limit=50):
        return await self.db.posts.find().sort("created_at", -1).limit(limit).to_list(length=limit)

    async def count_posts(self):
        return await self.db.posts.count_documents({})

    async def delete_post(self, post_id):
        return await self.db.posts.delete_one({"post_id": post_id})

    async def save_batch(self, batch_id, title, file_ids, file_names):
        return await self.db.batch_links.insert_one({
            "batch_id": batch_id,
            "title": title,
            "file_ids": file_ids,
            "file_names": file_names,
            "created_at": datetime.utcnow(),
        })

    async def get_batch(self, batch_id):
        return await self.db.batch_links.find_one({"batch_id": batch_id})

    async def count_batches(self):
        return await self.db.batch_links.count_documents({})

    async def delete_batch(self, batch_id):
        return await self.db.batch_links.delete_one({"batch_id": batch_id})

    async def save_schedule(self, schedule_id, title, post_data, send_at):
        return await self.db.schedules.insert_one({
            "schedule_id": schedule_id,
            "title": title,
            "post_data": post_data,
            "send_at": send_at,
            "sent": False,
            "created_at": datetime.utcnow(),
        })

    async def get_pending_schedules(self):
        return await self.db.schedules.find(
            {"sent": False, "send_at": {"$lte": datetime.utcnow()}}
        ).to_list(length=50)

    async def get_all_schedules(self, limit=50):
        return await self.db.schedules.find().sort("send_at", -1).limit(limit).to_list(length=limit)

    async def count_schedules(self):
        return await self.db.schedules.count_documents({"sent": False})

    async def mark_schedule_sent(self, schedule_id):
        await self.db.schedules.update_one(
            {"schedule_id": schedule_id}, {"$set": {"sent": True}}
        )

    async def delete_schedule(self, schedule_id):
        return await self.db.schedules.delete_one({"schedule_id": schedule_id})

    async def delete_all_schedules(self):
        return await self.db.schedules.delete_many({})

    async def set_maintenance(self, enabled):
        await self.db.settings.update_one(
            {"_id": "maintenance"}, {"$set": {"enabled": enabled}}, upsert=True
        )

    async def get_maintenance(self):
        setting = await self.db.settings.find_one({"_id": "maintenance"})
        return setting.get("enabled", False) if setting else False

    async def get_stats(self):
        posts = await self.db.posts.count_documents({})
        users = await self.db.users.count_documents({})
        schedules = await self.db.schedules.count_documents({"sent": False})
        batches = await self.db.batch_links.count_documents({})
        return {
            "posts": posts,
            "users": users,
            "scheduled": schedules,
            "batch_links": batches,
        }


db = Database()
