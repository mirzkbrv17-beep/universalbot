import json
import logging
import time

DAY = 86400
store = None  # main.py da yaratiladi


class MemDB:
    """Baza ulanmagan bo'lsa: xotirada + data.json (Render qayta ishga tushsa o'chadi)."""

    FILE = "data.json"

    def __init__(self):
        self.users, self.tests, self.results, self.starts = {}, {}, {}, 0
        self._last_save = 0.0
        try:
            with open(self.FILE) as f:
                d = json.load(f)
            self.users, self.tests = d.get("users", {}), d.get("tests", {})
            self.results, self.starts = d.get("results", {}), d.get("starts", 0)
        except Exception:
            pass

    def _save(self, force=False):
        if not force and time.time() - self._last_save < 30:
            return
        self._last_save = time.time()
        try:
            with open(self.FILE, "w") as f:
                json.dump({"users": self.users, "tests": self.tests,
                           "results": self.results, "starts": self.starts}, f)
        except Exception:
            logging.exception("save")

    async def touch(self, uid, name, username, start=False):
        now = time.time()
        u = self.users.setdefault(str(uid), {"first_seen": now, "starts": 0})
        u.update(name=name, username=username, last_seen=now)
        if start:
            u["starts"] += 1
            self.starts += 1
        self._save(force=start)

    async def stats(self):
        now = time.time()
        us = self.users.values()
        return {
            "total": len(self.users),
            "started": sum(1 for u in us if u.get("starts", 0) > 0),
            "starts": self.starts,
            "active24": sum(1 for u in us if u.get("last_seen", 0) >= now - DAY),
        }

    async def user_ids(self):
        return [int(k) for k in self.users]

    async def put_test(self, t):
        self.tests[t["_id"]] = t
        self._save(force=True)

    async def get_test(self, code):
        return self.tests.get(code)

    async def tests_by_owner(self, uid):
        return [t for t in self.tests.values() if t["owner"] == uid]

    async def put_result(self, r):
        self.results[r["_id"]] = r
        self._save(force=True)

    async def get_result(self, code, uid):
        return self.results.get(f"{code}:{uid}")

    async def results_for(self, code):
        return [r for r in self.results.values() if r["code"] == code]


class MongoDB:
    def __init__(self, url):
        from motor.motor_asyncio import AsyncIOMotorClient

        self.d = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)["universal_bot"]

    async def touch(self, uid, name, username, start=False):
        now = time.time()
        upd = {
            "$set": {"name": name, "username": username, "last_seen": now},
            "$setOnInsert": {"first_seen": now},
        }
        if start:
            upd["$inc"] = {"starts": 1}
        else:
            upd["$setOnInsert"]["starts"] = 0
        await self.d.users.update_one({"_id": uid}, upd, upsert=True)
        if start:
            await self.d.meta.update_one({"_id": "starts"}, {"$inc": {"n": 1}}, upsert=True)

    async def stats(self):
        now = time.time()
        m = await self.d.meta.find_one({"_id": "starts"})
        return {
            "total": await self.d.users.count_documents({}),
            "started": await self.d.users.count_documents({"starts": {"$gt": 0}}),
            "starts": (m or {}).get("n", 0),
            "active24": await self.d.users.count_documents({"last_seen": {"$gte": now - DAY}}),
        }

    async def user_ids(self):
        return [d["_id"] async for d in self.d.users.find({}, {"_id": 1})]

    async def put_test(self, t):
        await self.d.tests.replace_one({"_id": t["_id"]}, t, upsert=True)

    async def get_test(self, code):
        return await self.d.tests.find_one({"_id": code})

    async def tests_by_owner(self, uid):
        return [d async for d in self.d.tests.find({"owner": uid})]

    async def put_result(self, r):
        await self.d.results.replace_one({"_id": r["_id"]}, r, upsert=True)

    async def get_result(self, code, uid):
        return await self.d.results.find_one({"_id": f"{code}:{uid}"})

    async def results_for(self, code):
        return [d async for d in self.d.results.find({"code": code})]
