"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import json
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from contextlib import asynccontextmanager
from typing import Annotated, Generator

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    # Setup MongoDB connection during startup
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    
    # Store the client in app state for easier access and dependency injection
    app.state.mongo_client = client
    app.state.db = client.mergington_high
    
    # Load activities from JSON file and populate database if needed
    await initialize_database(app.state.db.activities)
    
    yield
    
    # Cleanup on shutdown
    client.close()
    print("MongoDB connection closed")

async def initialize_database(collection: AsyncIOMotorCollection):
    """Initialize the database with activities from the JSON file if it's empty."""
    # Load activities from JSON file
    activities_file = Path(__file__).parent / "activities.json"
    with open(activities_file, "r") as f:
        initial_activities = json.load(f)
    
    # Check if the collection already has data
    count = await collection.count_documents({})
    print(f"Found {count} existing activities in the database")
    
    # Reset database to fix duplicate entries (only for development)
    if count > 10:  # If we have more than expected (indicating duplicates)
        print("Detected possible duplicates, dropping collection")
        await collection.drop()
        count = 0  # Reset count since we dropped the collection
    
    # Only populate if the collection is empty
    if count == 0:
        print("Populating database with initial activities")
        # Pre-populate with initial activities using activity name as _id (key)
        for name, details in initial_activities.items():
            await collection.insert_one({"_id": name, **details})

# Database dependency - use this in route handlers
async def get_db():
    """Dependency to get the database from app state"""
    # In a real app, you would want to handle the case where the app state is not initialized
    # For this example, we assume the lifespan function has already set up the state
    from fastapi import Request
    request = Request.get_current()
    return request.app.state.db

async def get_activities_collection() -> AsyncIOMotorCollection:
    """
    Dependency that provides the activities collection.
    This pattern allows for better testability and separation of concerns.
    """
    db = await get_db()
    return db.activities

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
async def get_activities(collection: Annotated[AsyncIOMotorCollection, Depends(get_activities_collection)]):
    """Get all activities from MongoDB"""
    activities_cursor = collection.find({})
    activities_dict = {}
    
    async for activity in activities_cursor:
        name = activity.pop("_id")  # Use the _id as the activity name
        activities_dict[name] = activity
        
    return activities_dict


@app.post("/activities/{activity_name}/signup")
async def signup_for_activity(
    activity_name: str, 
    request: Request,
    collection: Annotated[AsyncIOMotorCollection, Depends(get_activities_collection)]
):
    """Sign up a student for an activity"""
    data = await request.json()
    email = data.get("email")

    # Retrieve the activity from MongoDB
    activity = await collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate if student is already signed up
    if email in activity["participants"]:
        raise HTTPException(status_code=400, detail="Already signed up for this activity")

    # Validate if activity is full
    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    # Add the student to the activity
    await collection.update_one(
        {"_id": activity_name},
        {"$push": {"participants": email}}
    )
    return {"message": f"Signed up {email} for {activity_name}"}


@app.post("/activities/{activity_name}/unregister")
async def unregister_participant(
    activity_name: str, 
    request: Request,
    collection: Annotated[AsyncIOMotorCollection, Depends(get_activities_collection)]
):
    """Unregister a student from an activity"""
    data = await request.json()
    email = data.get("email")

    # Retrieve the activity from MongoDB
    activity = await collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate if student is registered for the activity
    if email not in activity["participants"]:
        raise HTTPException(status_code=400, detail="Participant not found in this activity")

    # Remove the student from the activity
    await collection.update_one(
        {"_id": activity_name},
        {"$pull": {"participants": email}}
    )
    return {"message": f"Unregistered {email} from {activity_name}"}


@app.get("/db-status")
async def get_db_status(
    collection: Annotated[AsyncIOMotorCollection, Depends(get_activities_collection)],
    db = Depends(get_db)
):
    """Check database status - for debugging purposes"""
    count = await collection.count_documents({})
    return {
        "activities_count": count,
        "connection_status": "Connected" if db else "Not connected",
        "database_name": db.name if db else "Not available"
    }
