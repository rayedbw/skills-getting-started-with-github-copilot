"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import json
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager

# Global variable to hold the MongoDB collection
activities_collection = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    global activities_collection
    
    # Setup MongoDB connection during startup
    mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = mongo_client.mergington_high
    activities_collection = db.activities
    
    # Load activities from JSON file
    activities_file = Path(__file__).parent / "activities.json"
    with open(activities_file, "r") as f:
        initial_activities = json.load(f)
        
    # Check if the collection already has data
    count = await activities_collection.count_documents({})
    print(f"Found {count} existing activities in the database")
    
    # Reset database to fix duplicate entries (only for development)
    if count > 10:  # If we have more than expected (indicating duplicates)
        print("Detected possible duplicates, dropping collection")
        await db.drop_collection("activities")
        # Recreate the collection reference
        activities_collection = db.activities
        count = 0  # Reset count since we dropped the collection
    
    # Only populate if the collection is empty
    if count == 0:
        print("Populating database with initial activities")
        # Pre-populate with initial activities using activity name as _id (key)
        for name, details in initial_activities.items():
            await activities_collection.insert_one({"_id": name, **details})
    
    yield
    
    # Cleanup on shutdown
    mongo_client.close()
    print("MongoDB connection closed")

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities",
              lifespan=lifespan)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
async def get_activities():
    """Get all activities from MongoDB"""
    activities_cursor = activities_collection.find({})
    activities_dict = {}
    
    async for activity in activities_cursor:
        name = activity.pop("_id")  # Use the _id as the activity name
        activities_dict[name] = activity
        
    return activities_dict


@app.post("/activities/{activity_name}/signup")
async def signup_for_activity(activity_name: str, request: Request):
    """Sign up a student for an activity"""
    data = await request.json()
    email = data.get("email")

    # Retrieve the activity from MongoDB
    activity = await activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate if student is already signed up
    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Already signed up for this activity")

    # Validate if activity is full
    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    # Add the student to the activity
    await activities_collection.update_one(
        {"_id": activity_name},
        {"$push": {"participants": email}}
    )
    return {"message": f"Signed up {email} for {activity_name}"}


@app.post("/activities/{activity_name}/unregister")
async def unregister_participant(activity_name: str, request: Request):
    """Unregister a student from an activity"""
    data = await request.json()
    email = data.get("email")

    # Retrieve the activity from MongoDB
    activity = await activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate if student is registered for the activity
    if email not in activity["participants"]:
        raise HTTPException(status_code=400, detail="Participant not found in this activity")

    # Remove the student from the activity
    await activities_collection.update_one(
        {"_id": activity_name},
        {"$pull": {"participants": email}}
    )
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.get("/db-status")
async def get_db_status():
    """Check database status - for debugging purposes"""
    count = await activities_collection.count_documents({})
    return {
        "activities_count": count,
        "connection_status": "Connected" if activities_collection else "Not connected"
    }
