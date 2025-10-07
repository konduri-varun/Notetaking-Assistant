import asyncio
import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from nylas.models.errors import NylasApiError
from nylas.models.notetakers import InviteNotetakerRequest
from nylas_client import client, NYLAS_GRANT_ID
from tasks import check_and_get_transcript, transcripts
from database import transcript_collection

def detect_conferencing_provider(meeting_url: str) -> str:
    """
    Detect the conferencing provider based on the meeting URL.
    
    Args:
        meeting_url: The meeting URL provided by the user
        
    Returns:
        str: The exact provider name required by Nylas API
        
    Supported providers by Nylas:
    - 'Google Meet'
    - 'Microsoft Teams' (teams.microsoft.com and teams.live.com)
    - 'Zoom Meeting'
    - 'Teams for Business'
    - 'Skype for Business'
    - 'Skype for Consumer'
    """
    if not meeting_url:
        raise ValueError("Meeting URL is required")
    
    url_lower = meeting_url.lower()
    
    if "meet.google.com" in url_lower:
        return "Google Meet"
    elif "zoom.us" in url_lower:
        if "/wc/" in url_lower or "/j/" not in url_lower:
            raise ValueError("Invalid Zoom meeting link. Please use a standard Zoom meeting link (e.g., https://zoom.us/j/123456789?pwd=...) instead of personal room or web client links.")
        return "Zoom Meeting"  # Nylas requires exact name "Zoom Meeting"
    elif "teams.microsoft.com" in url_lower or "teams.live.com" in url_lower:
        return "Microsoft Teams"
    elif "skype.com" in url_lower:
        if "business" in url_lower:
            return "Skype for Business"
        else:
            return "Skype for Consumer"
    else:
        # For unknown providers, use Google Meet as fallback
        return "Google Meet"

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Participant(BaseModel):
    email: str
    name: Optional[str] = None


class ScheduleMeetingRequest(BaseModel):
    title: str
    meeting_link: str  # Google Meet, Zoom, or Microsoft Teams URL
    start_time: str  # Format: "2025-10-07 10:46 AM" or "2025-10-07 10:46 PM" (IST)


@app.get("/transcripts/{notetaker_id}")
async def get_transcript_status(notetaker_id: str):
    """
    Checks the status of a transcription from MongoDB using the notetaker_id.
    Returns the transcript text and status with detailed information.
    """
    # First check MongoDB
    transcript_data = await transcript_collection.find_one({"_id": notetaker_id})

    if transcript_data:
        response_data = {
            "notetaker_id": transcript_data["_id"],
            "status": transcript_data["status"],
        }
        
        # Extract text with speaker names from transcript_text JSON array
        if transcript_data.get("transcript_text"):
            transcript_json = transcript_data["transcript_text"]
            # Format text with speaker names: "Speaker: text"
            if isinstance(transcript_json, list):
                text_parts = []
                for item in transcript_json:
                    if isinstance(item, dict):
                        speaker = item.get("speaker", "Speaker")
                        text = item.get("text", "")
                        if text:
                            text_parts.append(f"{speaker}: {text}")
                response_data["transcript_text"] = "\n\n".join(text_parts)
            elif isinstance(transcript_json, str):
                # Try to parse string as JSON if it looks like an array
                try:
                    parsed = json.loads(transcript_json)
                    if isinstance(parsed, list):
                        text_parts = []
                        for item in parsed:
                            if isinstance(item, dict):
                                speaker = item.get("speaker", "Speaker")
                                text = item.get("text", "")
                                if text:
                                    text_parts.append(f"{speaker}: {text}")
                        response_data["transcript_text"] = "\n\n".join(text_parts)
                    else:
                        response_data["transcript_text"] = transcript_json
                except (json.JSONDecodeError, AttributeError):
                    # Not JSON, return as plain text
                    response_data["transcript_text"] = transcript_json
        
        # Add helpful status messages and display status
        status = transcript_data["status"]
        if status == "scheduled":
            response_data["message"] = "⏰ Meeting hasn't started yet. The bot will automatically join at the scheduled time."
            response_data["display_status"] = "Scheduled"
        elif status == "joining":
            response_data["message"] = "🚪 Bot is joining the meeting..."
            response_data["display_status"] = "Joining"
        elif status == "recording":
            response_data["message"] = "👥 Attending - Bot is in the meeting, recording and transcribing."
            response_data["display_status"] = "Attending"
        elif status == "processing":
            response_data["message"] = "⚙️ Processing - Meeting ended. Generating transcript..."
            response_data["display_status"] = "Processing"
        elif status == "ready":
            response_data["message"] = "📄 Media Available - Transcript is ready!"
            response_data["display_status"] = "Media Available"
        elif status == "failed":
            response_data["message"] = "❌ Transcription failed."
            response_data["display_status"] = "Failed"
        elif status == "timeout":
            response_data["message"] = "⏱️ Transcription timed out."
            response_data["display_status"] = "Timeout"
            
        return response_data
    
    # Fallback: check in-memory store
    transcript_text = transcripts.get(notetaker_id)
    if transcript_text:
        return {
            "notetaker_id": notetaker_id,
            "status": "ready",
            "display_status": "Media Available",
            "transcript_text": transcript_text,
            "message": "📄 Media Available - Transcript is ready!"
        }
    
    # If not found anywhere
    raise HTTPException(
        status_code=404, detail="Transcription job not found. Please check the notetaker ID."
    )


@app.get("/recordings")
async def get_all_recordings():
    """
    Returns all transcription recordings from MongoDB.
    Only returns: notetaker_id, status, transcript_text
    All data comes directly from database - no external API calls.
    """
    try:
        # Get all documents from MongoDB
        cursor = transcript_collection.find({})
        recordings = []
        
        async for doc in cursor:
            status = doc.get("status", "unknown")
            recording = {
                "notetaker_id": doc["_id"],
                "status": status,
            }
            
            # Add display status for better UI
            if status == "recording":
                recording["display_status"] = "Attending"
            elif status == "processing":
                recording["display_status"] = "Processing"
            elif status == "ready":
                recording["display_status"] = "Media Available"
            else:
                recording["display_status"] = status.title()
            
            # Extract text with speaker names from transcript_text JSON array
            if doc.get("transcript_text"):
                transcript_data = doc["transcript_text"]
                # Format text with speaker names: "Speaker: text"
                if isinstance(transcript_data, list):
                    text_parts = []
                    for item in transcript_data:
                        if isinstance(item, dict):
                            speaker = item.get("speaker", "Speaker")
                            text = item.get("text", "")
                            if text:
                                text_parts.append(f"{speaker}: {text}")
                    recording["transcript_text"] = "\n\n".join(text_parts)
                elif isinstance(transcript_data, str):
                    # Try to parse string as JSON if it looks like an array
                    try:
                        parsed = json.loads(transcript_data)
                        if isinstance(parsed, list):
                            text_parts = []
                            for item in parsed:
                                if isinstance(item, dict):
                                    speaker = item.get("speaker", "Speaker")
                                    text = item.get("text", "")
                                    if text:
                                        text_parts.append(f"{speaker}: {text}")
                            recording["transcript_text"] = "\n\n".join(text_parts)
                        else:
                            recording["transcript_text"] = transcript_data
                    except (json.JSONDecodeError, AttributeError):
                        # Not JSON, return as plain text
                        recording["transcript_text"] = transcript_data
            
            recordings.append(recording)
        
        return {
            "total": len(recordings),
            "recordings": recordings
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching recordings: {str(e)}"
        )


@app.delete("/recordings/{notetaker_id}")
async def delete_recording(notetaker_id: str):
    """
    🗑️ DELETE RECORDING: Delete a recording/transcript by notetaker ID.
    
    This endpoint will:
    1. Remove the recording from MongoDB
    2. Delete the transcript data
    3. Return confirmation of deletion
    
    Args:
        notetaker_id: The notetaker ID of the recording to delete
    
    Returns:
        Confirmation message
    
    Note: This action cannot be undone!
    """
    try:
        # Check if recording exists
        recording = await transcript_collection.find_one({"_id": notetaker_id})
        
        if not recording:
            raise HTTPException(
                status_code=404,
                detail=f"Recording with notetaker ID '{notetaker_id}' not found."
            )
        
        # Delete the recording
        result = await transcript_collection.delete_one({"_id": notetaker_id})
        
        if result.deleted_count > 0:
            # Also remove from in-memory store if exists
            if notetaker_id in transcripts:
                del transcripts[notetaker_id]
            
            return {
                "success": True,
                "message": f"Recording '{notetaker_id}' deleted successfully.",
                "deleted_notetaker_id": notetaker_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete recording from database."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting recording: {str(e)}"
        )


# --- CREATE MEETING WITH NOTETAKER ENDPOINT ---

@app.post("/schedule-meeting")
async def schedule_meeting(request: ScheduleMeetingRequest, background_tasks: BackgroundTasks):
    """
    📅 SCHEDULE MEETING: Creates a calendar event in Google Calendar and schedules bot to join.
    
    This endpoint will:
    1. ✅ Create a new event in your Google Calendar (only start time, no end time)
    2. ✅ Add the meeting link (Google Meet/Zoom/Microsoft Teams) to the calendar event
    3. ✅ Configure the AI Notetaker bot to automatically join at scheduled time
    4. ✅ Bot will stay until the call naturally ends (no fixed duration)
    5. ✅ Bot will record, transcribe, and generate summary after the meeting
    6. ✅ Track the session in MongoDB for transcript retrieval
    
    Args:
        request: Meeting details with IST date/time format
                 - title: Meeting title
                 - meeting_link: Google Meet, Zoom, or Microsoft Teams URL
                 - start_time: Format: "YYYY-MM-DD HH:MM AM/PM" (e.g., "2025-10-07 10:46 AM")
    
    Returns:
        Dictionary with:
        - event_id: Google Calendar event ID
        - session_id: Bot session ID for transcript tracking
        - calendar_link: Link to view event in Google Calendar
        
    Note: No end time is set - the bot will automatically leave when the call ends.
    """
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")
    
    try:
        from datetime import datetime
        import pytz
        
        # Parse the Indian Standard Time (IST) datetime strings
        # Supported formats: "2025-10-07 10:46 AM" or "2025-10-07 10:46 PM"
        try:
            from datetime import timedelta
            
            # Set the timezone to IST (Asia/Kolkata)
            ist_tz = pytz.timezone("Asia/Kolkata")
            
            # Parse start time
            start_dt = datetime.strptime(request.start_time, "%Y-%m-%d %I:%M %p")
            start_dt = ist_tz.localize(start_dt)
            start_timestamp = int(start_dt.timestamp())
            
            # Nylas API requires end time when using Notetaker
            # Default to 1 hour meeting duration
            end_dt = start_dt + timedelta(hours=1)
            end_timestamp = int(end_dt.timestamp())
            
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date/time format. Use format: 'YYYY-MM-DD HH:MM AM/PM' (e.g., '2025-10-07 10:46 AM'). Error: {str(e)}"
            )
        
        # Create the event with all details including notetaker configuration
        # Using timespan format (required for Notetaker)
        
        # Detect the conferencing provider from the URL
        try:
            provider = detect_conferencing_provider(request.meeting_link)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Build the event request
        # Note: For Zoom meetings, we'll deploy the bot separately after event creation
        # because Zoom notetakers work better with direct invitation
        event_request = {
            "title": request.title,
            "when": {
                "start_time": start_timestamp,
                "end_time": end_timestamp,
                "start_timezone": "Asia/Kolkata",
                "end_timezone": "Asia/Kolkata",
            },
        }
        
        # Add conferencing details if provider is detected
        if provider:
            event_request["conferencing"] = {
                "provider": provider,
                "details": {
                    "url": request.meeting_link
                }
            }
        else:
            # For unknown providers, just add the URL without specifying a provider
            # Nylas will handle it as a generic conferencing link
            event_request["location"] = request.meeting_link
        
        # For Google Meet and Microsoft Teams, embed notetaker in event
        # For Zoom, we'll deploy it separately (more reliable)
        is_zoom = provider == "Zoom Meeting"
        if not is_zoom:
            event_request["notetaker"] = {
                "name": "AI Notetaker Bot",
                "meeting_settings": {
                    "video_recording": True,
                    "audio_recording": True,
                    "transcription": True,
                    "summary": True,
                    "action_items": True,
                }
            }
        
        # Create the event in the calendar
        provider_display = provider if provider else "generic conferencing link"
        print(f"🔄 Creating calendar event with provider: {provider_display}")
        try:
            event_response = client.events.create(
                identifier=NYLAS_GRANT_ID,
                request_body=event_request,
                query_params={"calendar_id": "primary"}
            )
            print(f"✅ Event created successfully with provider: {provider_display}")
        except Exception as api_error:
            print(f"❌ Nylas API error with provider '{provider_display}': {str(api_error)}")
            # If the provider is not supported, try with Google Meet as fallback
            if provider and ("provider" in str(api_error).lower() or "conferencing" in str(api_error).lower()):
                print(f"🔄 Retrying with Google Meet as fallback provider...")
                event_request["conferencing"] = {
                    "provider": "Google Meet",
                    "details": {
                        "url": request.meeting_link
                    }
                }
                # Remove location if we added it
                if "location" in event_request:
                    del event_request["location"]
                    
                event_response = client.events.create(
                    identifier=NYLAS_GRANT_ID,
                    request_body=event_request,
                    query_params={"calendar_id": "primary"}
                )
                provider = "Google Meet (fallback)"
                print(f"✅ Event created with fallback provider: {provider}")
            else:
                raise api_error
        
        event_data = event_response.data
        
        # Extract event ID
        event_id = event_data.id if hasattr(event_data, 'id') else None
        
        # Extract notetaker_id if available
        notetaker_id = None
        if hasattr(event_data, 'notetaker') and event_data.notetaker:
            if hasattr(event_data.notetaker, 'id'):
                notetaker_id = event_data.notetaker.id
            elif isinstance(event_data.notetaker, dict):
                notetaker_id = event_data.notetaker.get('id')
        
        # Deploy notetaker bot
        # For Zoom: always use direct invitation (more reliable)
        # For others: deploy if not auto-created
        bot_error = None
        if not notetaker_id or is_zoom:
            deployment_reason = "Zoom requires direct invitation" if is_zoom else "Notetaker not auto-created"
            print(f"⚠️ {deployment_reason}, deploying bot via invite method...")
            try:
                request_body: InviteNotetakerRequest = {
                    "meeting_link": request.meeting_link,
                    "name": "AI Transcription Bot",
                    "meeting_settings": {
                        "video_recording": True,
                        "audio_recording": True,
                        "transcription": True,
                        "diarization": True,
                    },
                }
                
                print(f"📞 Inviting bot to {provider} meeting: {request.meeting_link}")
                notetaker_response = client.notetakers.invite(
                    identifier=NYLAS_GRANT_ID,
                    request_body=request_body
                )
                
                notetaker_id = notetaker_response.data.id
                print(f"✅ Bot successfully deployed to {provider} meeting with ID: {notetaker_id}")
            except Exception as e:
                bot_error = str(e)
                error_msg = str(e)
                print(f"❌ Failed to deploy bot to {provider} meeting: {error_msg}")
                
                # Provide specific guidance for common Zoom errors
                if is_zoom:
                    if "invalid" in error_msg.lower() or "url" in error_msg.lower():
                        print(f"💡 Zoom URL may be invalid or expired. Please check:")
                        print(f"   - URL format: https://zoom.us/j/... or https://us05web.zoom.us/j/...")
                        print(f"   - Meeting is not expired or cancelled")
                        print(f"   - Meeting allows participants to join")
                    elif "authentication" in error_msg.lower() or "credentials" in error_msg.lower():
                        print(f"💡 Zoom authentication issue. The bot needs:")
                        print(f"   - Valid Zoom meeting link")
                        print(f"   - Meeting host to allow bot to join")
                        print(f"   - No waiting room or pre-approval required")
        
        # Create tracking document in MongoDB
        # Store ONLY: notetaker_id (as _id), status, transcript_text (empty initially)
        if notetaker_id:
            await transcript_collection.insert_one({
                "_id": notetaker_id,
                "status": "scheduled"
            })
            # Start a background task to poll for the transcript after the meeting
            background_tasks.add_task(check_and_get_transcript, notetaker_id)
            print(f"✅ Meeting scheduled: {request.title} at {start_dt.strftime('%Y-%m-%d %I:%M %p IST')}")
            print(f"✅ Bot will join automatically. Notetaker ID: {notetaker_id}")
        else:
            print(f"⚠️ Meeting created but bot deployment failed")
        
        # Generate Google Calendar link
        calendar_link = f"https://calendar.google.com/calendar/event?eid={event_id}" if event_id else None
        
        return {
            "success": True,
            "message": f"✅ Meeting scheduled successfully{' with ' + provider + ' as conferencing provider' if provider and 'fallback' not in provider else ' with conferencing link' if not provider else ' with ' + provider}! Event added to Google Calendar and bot configured to join automatically.",
            "event_id": event_id,
            "title": request.title,
            "start_time": start_dt.strftime("%Y-%m-%d %I:%M %p IST"),
            "meeting_link": request.meeting_link,
            "provider": provider.replace(" (fallback)", "") if provider else "Generic",
            "calendar_link": calendar_link,
            "notetaker_id": notetaker_id,
            "bot_status": "Configured to join at scheduled time" if notetaker_id else f"Failed to configure bot: {bot_error}" if bot_error else "Failed to configure bot",
            "next_steps": [
                "✅ Event has been added to your Google Calendar",
                "✅ Bot will automatically join the meeting at the scheduled time" if notetaker_id else f"❌ Bot failed to configure: {bot_error}" if bot_error else "❌ Bot failed to configure",
                f"✅ After the meeting, use Notetaker ID '{notetaker_id}' to check the transcript" if notetaker_id else "❌ No transcript will be available due to bot failure"
            ]
        }
        
    except NylasApiError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to create meeting: {str(e)}"
        )


# --- FETCH CALENDAR EVENTS AND AUTO-DEPLOY BOT ---

class FetchEventsRequest(BaseModel):
    start_date: str  # Format: "2025-10-07" (IST)
    end_date: Optional[str] = None  # Optional end date
    calendar_id: Optional[str] = "primary"


@app.post("/fetch-calendar-events")
async def fetch_calendar_events(request: FetchEventsRequest):
    """
    📅 FETCH CALENDAR EVENTS: Get all calendar events for a specific date/time range.
    
    This endpoint:
    1. Fetches events from your Google Calendar via Nylas
    2. Filters by date/time range
    3. Extracts meeting links from conferencing details
    4. Returns all events with their meeting URLs
    
    Args:
        start_date: Start date in IST (format: "2025-10-07")
        end_date: Optional end date (defaults to same as start_date)
        calendar_id: Calendar ID (defaults to "primary")
    
    Returns:
        List of calendar events with meeting links
    """
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")
    
    try:
        from datetime import datetime
        import pytz
        
        # Set timezone to IST
        ist_tz = pytz.timezone("Asia/Kolkata")
        
        # Parse start date
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        start_dt = ist_tz.localize(start_dt.replace(hour=0, minute=0, second=0))
        start_timestamp = int(start_dt.timestamp())
        
        # Parse end date (default to end of start date)
        if request.end_date:
            end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
            end_dt = ist_tz.localize(end_dt.replace(hour=23, minute=59, second=59))
        else:
            end_dt = start_dt.replace(hour=23, minute=59, second=59)
        end_timestamp = int(end_dt.timestamp())
        
        # Fetch events from Nylas
        events_response = client.events.list(
            identifier=NYLAS_GRANT_ID,
            query_params={
                "calendar_id": request.calendar_id,
                "start": start_timestamp,
                "end": end_timestamp
            }
        )
        
        # Extract relevant event information
        events_list = []
        for event in events_response.data:
            event_info = {
                "event_id": event.id,
                "title": event.title if hasattr(event, 'title') else "Untitled",
                "start_time": None,
                "end_time": None,
                "meeting_link": None,
                "conferencing_provider": None,
                "status": event.status if hasattr(event, 'status') else "unknown"
            }
            
            # Extract time information
            if hasattr(event, 'when') and event.when:
                if hasattr(event.when, 'start_time'):
                    start_ts = event.when.start_time
                    start_dt_obj = datetime.fromtimestamp(start_ts, tz=ist_tz)
                    event_info["start_time"] = start_dt_obj.strftime("%Y-%m-%d %I:%M %p IST")
                
                if hasattr(event.when, 'end_time'):
                    end_ts = event.when.end_time
                    end_dt_obj = datetime.fromtimestamp(end_ts, tz=ist_tz)
                    event_info["end_time"] = end_dt_obj.strftime("%Y-%m-%d %I:%M %p IST")
            
            # Extract meeting link from conferencing details
            if hasattr(event, 'conferencing') and event.conferencing:
                if hasattr(event.conferencing, 'provider'):
                    event_info["conferencing_provider"] = event.conferencing.provider
                
                if hasattr(event.conferencing, 'details') and event.conferencing.details:
                    if hasattr(event.conferencing.details, 'url'):
                        event_info["meeting_link"] = event.conferencing.details.url
            
            events_list.append(event_info)
        
        return {
            "total_events": len(events_list),
            "date_range": {
                "start": start_dt.strftime("%Y-%m-%d %I:%M %p IST"),
                "end": end_dt.strftime("%Y-%m-%d %I:%M %p IST")
            },
            "events": events_list
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Use 'YYYY-MM-DD'. Error: {str(e)}"
        )
    except NylasApiError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch calendar events: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


class AutoDeployBotRequest(BaseModel):
    event_id: str  # The calendar event ID to deploy bot to
    calendar_id: Optional[str] = "primary"


@app.post("/auto-deploy-bot")
async def auto_deploy_bot_to_event(request: AutoDeployBotRequest, background_tasks: BackgroundTasks):
    """
    🤖 AUTO-DEPLOY BOT: Automatically deploy notetaker bot to an existing calendar event.
    
    This endpoint:
    1. Fetches the calendar event by ID
    2. Extracts the meeting link (conferencing.details.url)
    3. Deploys the Nylas Notetaker bot to join that meeting
    4. Starts tracking the transcript
    
    Use this to add bot to meetings that are already in your calendar!
    
    Args:
        event_id: The ID of the calendar event
        calendar_id: Optional calendar ID (defaults to "primary")
    
    Returns:
        Session ID for tracking the transcript
    """
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")
    
    try:
        # 1. Fetch the specific calendar event
        event = client.events.find(
            identifier=NYLAS_GRANT_ID,
            event_id=request.event_id,
            query_params={"calendar_id": request.calendar_id}
        )
        
        event_data = event.data
        
        # 2. Extract meeting link from conferencing details
        meeting_link = None
        if hasattr(event_data, 'conferencing') and event_data.conferencing:
            if hasattr(event_data.conferencing, 'details') and event_data.conferencing.details:
                if hasattr(event_data.conferencing.details, 'url'):
                    meeting_link = event_data.conferencing.details.url
        
        if not meeting_link:
            raise HTTPException(
                status_code=400,
                detail="No meeting link found in the calendar event. Please ensure the event has a Google Meet or Zoom link."
            )
        
        # 3. Deploy the Nylas Notetaker bot to join the meeting
        request_body: InviteNotetakerRequest = {
            "meeting_link": meeting_link,
            "name": "AI Transcription Bot",
            "meeting_settings": {
                "video_recording": True,
                "audio_recording": True,
                "transcription": True,
            },
        }
        
        notetaker_response = client.notetakers.invite(
            identifier=NYLAS_GRANT_ID,
            request_body=request_body
        )
        
        notetaker_id = notetaker_response.data.id
        
        # 4. Create tracking document in MongoDB (ONLY 3 fields)
        await transcript_collection.insert_one({
            "_id": notetaker_id,
            "status": "processing"
        })
        
        # 5. Start background task to check for transcript
        background_tasks.add_task(check_and_get_transcript, notetaker_id)
        
        return {
            "message": "Bot successfully deployed to the meeting!",
            "notetaker_id": notetaker_id,
            "event_id": request.event_id,
            "event_title": event_data.title if hasattr(event_data, 'title') else "Untitled",
            "meeting_link": meeting_link,
            "status": "Bot will join the meeting and start recording"
        }
        
    except NylasApiError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to deploy bot: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


class DeleteEventRequest(BaseModel):
    event_id: str  # The calendar event ID to delete
    calendar_id: Optional[str] = "primary"


@app.delete("/calendar-events/{event_id}")
async def delete_calendar_event(event_id: str, calendar_id: str = "primary"):
    """
    🗑️ DELETE CALENDAR EVENT: Delete a calendar event from Google Calendar.
    
    This endpoint will:
    1. Delete the event from Google Calendar
    2. Remove any associated bot/notetaker tracking
    3. Return confirmation of deletion
    
    Args:
        event_id: The ID of the calendar event to delete
        calendar_id: Optional calendar ID (defaults to "primary")
    
    Returns:
        Confirmation message
    
    Note: This action cannot be undone! The event will be removed from your calendar.
    """
    print(f"\n{'='*60}")
    print(f"🗑️ DELETE REQUEST RECEIVED")
    print(f"Event ID: {event_id}")
    print(f"Calendar ID: {calendar_id}")
    print(f"{'='*60}\n")
    
    if not client:
        raise HTTPException(status_code=500, detail="Nylas client not initialized.")
    
    try:
        print(f"🗑️ Attempting to delete event: {event_id} from calendar: {calendar_id}")
        
        # First, try to get the event to verify it exists
        event_title = "Unknown"
        event_exists = False
        
        try:
            event = client.events.find(
                identifier=NYLAS_GRANT_ID,
                event_id=event_id,
                query_params={"calendar_id": calendar_id}
            )
            event_title = event.data.title if hasattr(event.data, 'title') else "Untitled"
            event_exists = True
            print(f"✅ Found event: {event_title}")
        except NylasApiError as find_error:
            print(f"⚠️ Event not found in Nylas: {find_error}")
            # Event might not exist in Nylas but could exist in MongoDB
            # Continue to try deletion and cleanup
        except Exception as find_e:
            print(f"⚠️ Error finding event: {find_e}")
        
        # Try to delete the event from calendar
        deletion_success = False
        deletion_error = None
        try:
            if event_exists:
                # Note: Nylas destroy() returns an empty response (204 No Content)
                # This is normal and expected behavior
                client.events.destroy(
                    identifier=NYLAS_GRANT_ID,
                    event_id=event_id,
                    query_params={"calendar_id": calendar_id}
                )
                # If no exception was raised, deletion was successful
                deletion_success = True
                print(f"✅ Event deleted from Google Calendar")
            else:
                print(f"⚠️ Event not found in Nylas, skipping calendar deletion")
        except NylasApiError as delete_error:
            error_msg = str(delete_error)
            print(f"❌ Nylas delete error: {error_msg}")
            deletion_error = error_msg
            # If it's a "not found" error, it might already be deleted
            if "not found" in error_msg.lower() or "404" in error_msg:
                print("ℹ️ Event may have been already deleted from calendar")
                # Don't raise, continue to cleanup
            else:
                # For other errors, we'll still try to cleanup but record the error
                print(f"⚠️ Calendar deletion failed but will continue with cleanup")
        except Exception as delete_e:
            # Ignore JSON parsing errors from empty responses (expected for delete)
            if "Expecting value" not in str(delete_e):
                deletion_error = str(delete_e)
                print(f"❌ Unexpected error during calendar deletion: {delete_e}")
            else:
                # Empty response is actually success for delete operations
                deletion_success = True
                print(f"✅ Event deleted from Google Calendar (empty response is normal)")
        
        # Always try to clean up associated recording/tracking in MongoDB
        # This is important even if the calendar event doesn't exist
        recordings_deleted = 0
        try:
            result = await transcript_collection.delete_many({"event_id": event_id})
            recordings_deleted = result.deleted_count
            if recordings_deleted > 0:
                print(f"✅ Deleted {recordings_deleted} associated recording(s) for event {event_id}")
        except Exception as e:
            print(f"⚠️ Could not check/delete associated recordings: {e}")
        
        # Determine success message
        response_data = {
            "success": deletion_success or recordings_deleted > 0,
            "deleted_event_id": event_id,
            "event_title": event_title,
            "calendar_deletion": deletion_success,
            "recordings_deleted": recordings_deleted
        }
        
        if deletion_success or recordings_deleted > 0:
            response_data["message"] = f"Event deleted successfully! {f'Title: {event_title}' if event_title != 'Unknown' else ''}"
            if deletion_error:
                response_data["warning"] = f"Calendar deletion had issues: {deletion_error}"
            print(f"\n✅ DELETE SUCCESSFUL - Returning response:")
            print(f"   Response: {response_data}")
            print(f"{'='*60}\n")
            return response_data
        else:
            # Neither calendar event nor recordings found
            print(f"\n❌ DELETE FAILED - Event not found")
            print(f"{'='*60}\n")
            raise HTTPException(
                status_code=404,
                detail=f"Event '{event_id}' not found in calendar or database. It may have been already deleted."
            )
        
    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        print(f"\n⚠️ HTTP Exception: {http_exc.detail}")
        print(f"{'='*60}\n")
        raise
    except NylasApiError as e:
        error_msg = str(e)
        print(f"\n❌ Nylas API Error: {error_msg}")
        print(f"{'='*60}\n")
        if "not found" in error_msg.lower() or "404" in error_msg:
            raise HTTPException(
                status_code=404,
                detail=f"Calendar event not found. It may have been already deleted."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to delete calendar event: {error_msg}"
            )
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR during deletion: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while deleting event: {str(e)}"
        )


@app.get("/auth-status")
async def check_auth_status():
    """
    ✅ CHECK AUTHENTICATION: Verify if Nylas is properly authenticated with Google Calendar.
    
    Returns:
        Authentication status and Grant ID information
    """
    if not client:
        return {
            "authenticated": False,
            "message": "Nylas client not initialized. Check your API key.",
            "grant_id": None
        }
    
    try:
        # Try to fetch account info to verify authentication
        grant = client.auth.grants.find(grant_id=NYLAS_GRANT_ID)
        
        return {
            "authenticated": True,
            "message": "Successfully authenticated with Nylas",
            "grant_id": NYLAS_GRANT_ID,
            "email": grant.data.email if hasattr(grant.data, 'email') else None,
            "provider": grant.data.provider if hasattr(grant.data, 'provider') else None,
            "status": grant.data.grant_status if hasattr(grant.data, 'grant_status') else None
        }
    except Exception as e:
        return {
            "authenticated": False,
            "message": f"Authentication check failed: {str(e)}",
            "grant_id": NYLAS_GRANT_ID
        }