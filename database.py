import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
from config import FIREBASE_CONFIG

class Database:
    def __init__(self):
        if not firebase_admin._apps and FIREBASE_CONFIG:
            cred = credentials.Certificate(FIREBASE_CONFIG)
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
        else:
            self.db = None
    
    # ==================== المستخدمين ====================
    def add_user(self, user_id: int, username: str, first_name: str):
        if not self.db:
            return
        ref = self.db.collection("users").document(str(user_id))
        if not ref.get().exists:
            ref.set({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now(timezone.utc),
                "is_banned": False,
                "checks_count": 0,
                "ok_count": 0
            })
            return True  # مستخدم جديد
        return False
    
    def get_user(self, user_id: int):
        if not self.db:
            return None
        doc = self.db.collection("users").document(str(user_id)).get()
        return doc.to_dict() if doc.exists else None
    
    def ban_user(self, user_id: int):
        if not self.db:
            return
        self.db.collection("users").document(str(user_id)).update({"is_banned": True})
    
    def unban_user(self, user_id: int):
        if not self.db:
            return
        self.db.collection("users").document(str(user_id)).update({"is_banned": False})
    
    def get_all_users(self):
        if not self.db:
            return []
        return [doc.to_dict() for doc in self.db.collection("users").stream()]
    
    def get_banned_users(self):
        return [u for u in self.get_all_users() if u.get("is_banned")]
    
    # ==================== الإحصائيات ====================
    def log_check(self, user_id: int, success: bool):
        if not self.db:
            return
        user_ref = self.db.collection("users").document(str(user_id))
        user_ref.update({
            "checks_count": firestore.Increment(1),
            "ok_count": firestore.Increment(1 if success else 0)
        })
        
        # إحصائيات عامة
        stats_ref = self.db.collection("stats").document("global")
        stats_ref.set({
            "total_checks": firestore.Increment(1),
            "total_ok": firestore.Increment(1 if success else 0),
            "last_check": datetime.now(timezone.utc)
        }, merge=True)
    
    def get_global_stats(self):
        if not self.db:
            return {"total_checks": 0, "total_ok": 0}
        doc = self.db.collection("stats").document("global").get()
        return doc.to_dict() if doc.exists else {"total_checks": 0, "total_ok": 0}
    
    # ==================== السجل ====================
    def add_history(self, user_id: int, account_data: dict):
        if not self.db:
            return
        self.db.collection("history").add({
            "user_id": user_id,
            **account_data,
            "checked_at": datetime.now(timezone.utc)
        })
    
    def get_user_history(self, user_id: int, limit: int = 10):
        if not self.db:
            return []
        docs = (self.db.collection("history")
                .where("user_id", "==", user_id)
                .order_by("checked_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream())
        return [doc.to_dict() for doc in docs]

db = Database()
