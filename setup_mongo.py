from mongodb_connection import get_db
import datetime

db = get_db()

# Collections
# users, events, event_categories, registrations_new, active_users, notifications, event_feedback, competitions, tech_fests

def seed():
    # Events
    if db.events.count_documents({}) == 0:
        db.events.insert_many([
            {
                "id": 1,
                "name": "Global Tech Summit 2026",
                "description": "The biggest tech conference of the year.",
                "category": "Technology",
                "department": "Computer Science",
                "event_date": "2026-05-15",
                "event_time": "10:00",
                "venue": "Main Hall",
                "price": 500,
                "image": None,
                "tech_fest_id": None
            },
            {
                "id": 2,
                "name": "Cultural Fest 2026",
                "description": "Celebrating diversity and art.",
                "category": "Culture",
                "department": "Arts",
                "event_date": "2026-06-20",
                "event_time": "18:00",
                "venue": "Campus Grounds",
                "price": 0,
                "image": None,
                "tech_fest_id": None
            }
        ])
        print("Events seeded.")

    # Event Categories
    if db.event_categories.count_documents({}) == 0:
        db.event_categories.insert_many([
            {"id": 1, "event_id": 1, "category_name": "Pro Ticket"},
            {"id": 2, "event_id": 1, "category_name": "Student Ticket"},
            {"id": 3, "event_id": 2, "category_name": "General Admission"}
        ])
        print("Categories seeded.")

    # Tech Fests
    if db.tech_fests.count_documents({}) == 0:
        db.tech_fests.insert_one({
            "id": 1,
            "name": "TechTronics 2026",
            "department": "Electronics",
            "description": "Innovation in Electronics.",
            "fest_date": "2026-04-25",
            "venue": "Lab Block",
            "image": None,
            "show_on_home": True
        })
        print("Tech Fests seeded.")

if __name__ == "__main__":
    seed()
