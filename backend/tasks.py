import asyncio
import httpx  # Import httpx for making HTTP requests
import json
from nylas.models.notetakers import NotetakerState
from nylas_client import client, NYLAS_GRANT_ID
from database import transcript_collection

# A simple in-memory store for transcripts (backup)
transcripts = {}


async def check_and_get_transcript(notetaker_id: str):
    """
    Checks the status of the notetaker and updates MongoDB with the transcript text.
    Args:
        notetaker_id: The ID of the notetaker to check.
    """
    print(f"🔄 Starting background task to monitor notetaker: {notetaker_id}")
    max_retries = 120  # Poll for up to 1 hour (120 * 30 seconds)
    retry_count = 0

    # Use an async HTTP client for fetching the transcript file
    async with httpx.AsyncClient() as http_client:
        while retry_count < max_retries:
            retry_count += 1
            try:
                notetaker = client.notetakers.find(
                    identifier=NYLAS_GRANT_ID, notetaker_id=notetaker_id
                )
                current_state = notetaker.data.state
                print(f"📊 Notetaker state for {notetaker_id}: {current_state} (Check #{retry_count})")
                
                # Update the status in MongoDB based on current state
                # Only 4 valid Nylas states: CONNECTING, ATTENDING, MEDIA_PROCESSING, MEDIA_AVAILABLE
                if current_state == NotetakerState.CONNECTING:
                    # Bot is connecting to the meeting
                    await transcript_collection.update_one(
                        {"_id": notetaker_id},
                        {"$set": {"status": "joining"}}
                    )
                elif current_state == NotetakerState.ATTENDING:
                    # Bot is in the meeting (Attending)
                    await transcript_collection.update_one(
                        {"_id": notetaker_id},
                        {"$set": {"status": "recording"}}
                    )
                elif current_state == NotetakerState.MEDIA_PROCESSING:
                    # Bot is processing the media after meeting ends
                    await transcript_collection.update_one(
                        {"_id": notetaker_id},
                        {"$set": {"status": "processing"}}
                    )
                
                if current_state == NotetakerState.MEDIA_AVAILABLE:
                    print(f"✅ Media available for {notetaker_id}! Fetching transcript...")
                    media = client.notetakers.get_media(
                        identifier=NYLAS_GRANT_ID, notetaker_id=notetaker_id
                    )
                    
                    # Debug: Print media structure to understand what's available
                    print(f"📊 Media object type: {type(media)}")
                    print(f"📊 Media data type: {type(media.data)}")
                    if hasattr(media.data, '__dict__'):
                        print(f"📊 Media data attributes: {media.data.__dict__.keys()}")
                    
                    transcript_data = None
                    transcript_text_combined = ""
                    
                    # Check if transcript exists and has URL
                    if hasattr(media.data, 'transcript') and media.data.transcript:
                        if hasattr(media.data.transcript, 'url') and media.data.transcript.url:
                            transcript_url = media.data.transcript.url
                            
                            # 1. Fetch the content from the URL
                            print(f"📥 Fetching transcript from URL: {transcript_url}")
                            print(f"🔗 URL host: {transcript_url.split('/')[2] if len(transcript_url.split('/')) > 2 else 'unknown'}")
                            try:
                                response = await http_client.get(transcript_url, timeout=60)
                                response.raise_for_status()  # Raise an exception for bad status codes
                                
                                print(f"📄 Received response with status: {response.status_code}")
                                print(f"📄 Response content length: {len(response.text)} characters")
                                
                                # Parse the response as JSON
                                try:
                                    raw_transcript = json.loads(response.text)
                                    print(f"📄 Parsed JSON successfully. Type: {type(raw_transcript)}")
                                    print(f"📄 Full transcript JSON: {json.dumps(raw_transcript, indent=2)}")
                                    
                                    # Handle Nylas transcript structure: {"object": "transcript", "type": "...", "transcript": [...]}
                                    if isinstance(raw_transcript, dict) and 'transcript' in raw_transcript:
                                        transcript_array = raw_transcript['transcript']
                                        print(f"📄 Found transcript array in wrapper object with {len(transcript_array)} entries")
                                    elif isinstance(raw_transcript, list):
                                        transcript_array = raw_transcript
                                        print(f"📄 Transcript is direct array with {len(transcript_array)} entries")
                                    else:
                                        transcript_array = [raw_transcript]
                                        print(f"📄 Transcript is single object, wrapped in array")
                                    
                                    # Extract text AND speaker, store as clean JSON array
                                    clean_transcript_array = []
                                    unique_speakers = set()
                                    for entry in transcript_array:
                                        if isinstance(entry, dict):
                                            # Direct structure: {"speaker": "...", "text": "...", "start": ..., "end": ...}
                                            segment_text = entry.get('text', '').strip()
                                            segment_speaker = entry.get('speaker', 'Speaker').strip()
                                            
                                            if segment_text:
                                                unique_speakers.add(segment_speaker)
                                                transcript_entry = {
                                                    "speaker": segment_speaker,
                                                    "text": segment_text
                                                }
                                                
                                                clean_transcript_array.append(transcript_entry)
                                                print(f"📝 Added transcript entry: {segment_speaker}: {segment_text[:50]}...")
                                            else:
                                                print(f"⚠️ Skipping empty text entry from speaker: {segment_speaker}")
                                        elif isinstance(entry, str):
                                            clean_transcript_array.append({
                                                "speaker": "Speaker",
                                                "text": entry.strip()
                                            })
                                            print(f"📝 Added string transcript entry: {entry[:50]}...")
                                    
                                    print(f"🎤 Detected speakers: {list(unique_speakers)}")
                                    
                                    # Store as JSON array (will be stored as array in MongoDB)
                                    if clean_transcript_array:
                                        transcript_data = clean_transcript_array
                                        print(f"✅ Successfully parsed transcript with {len(transcript_data)} entries for {notetaker_id}")
                                        # Log first entry for verification
                                        if len(transcript_data) > 0:
                                            first_entry = transcript_data[0]
                                            print(f"📝 First transcript entry sample: {first_entry}")
                                    else:
                                        print(f"⚠️ No valid transcript entries found after parsing")
                                        print(f"⚠️ Raw transcript array had {len(transcript_array)} items")
                                        print(f"⚠️ Sample of raw array: {transcript_array[:2] if len(transcript_array) > 0 else 'empty'}")
                                        
                                        # Provide helpful message about why transcript might be empty
                                        empty_reason = "Transcript was empty. Possible reasons:\\n"
                                        empty_reason += "• Meeting was too short (< 30 seconds)\\n"
                                        empty_reason += "• No one spoke during the meeting\\n"
                                        empty_reason += "• Transcription service couldn't detect clear audio\\n"
                                        empty_reason += "• Meeting platform doesn't support transcription for this type of meeting\\n"
                                        empty_reason += f"• For Zoom: Ensure transcription is enabled in meeting settings"
                                        
                                        transcript_data = [{
                                            "speaker": "System", 
                                            "text": f"Meeting recorded (ID: {notetaker_id}) but no transcript content available. {empty_reason}"
                                        }]
                                        print(f"💾 Storing informative message about empty transcript")
                                        
                                except json.JSONDecodeError as json_err:
                                    # If not valid JSON, store as plain text in array format
                                    transcript_data = [{"speaker": "Transcript", "text": response.text}]
                                    print(f"⚠️ JSON decode error: {json_err}. Stored response as plain text transcript for {notetaker_id}")
                                
                            except httpx.HTTPStatusError as http_e:
                                status_code = http_e.response.status_code if hasattr(http_e, 'response') else 'Unknown'
                                print(f"❌ HTTP error fetching transcript: {http_e}")
                                print(f"❌ Response status: {status_code}")
                                
                                # Provide specific guidance for common errors
                                if status_code == 401:
                                    print(f"❌ Authentication failed - check Nylas API key")
                                elif status_code == 403:
                                    print(f"❌ Access forbidden - check permissions for notetaker {notetaker_id}")
                                elif status_code == 404:
                                    print(f"❌ Transcript not found - may not be ready yet")
                                elif status_code == 429:
                                    print(f"❌ Rate limited - too many requests")
                                else:
                                    print(f"❌ HTTP error {status_code} - check Nylas API documentation")
                                    
                            except httpx.TimeoutException as timeout_e:
                                print(f"❌ Timeout error fetching transcript: {timeout_e}")
                                print(f"❌ Transcript URL may be slow or unresponsive")
                            except httpx.RequestError as req_e:
                                print(f"❌ Request error fetching transcript: {req_e}")
                                print(f"❌ Check network connectivity or Nylas API status")
                            except Exception as fetch_e:
                                print(f"❌ Unexpected error fetching transcript: {fetch_e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"⚠️ Transcript object exists but no URL found")
                    else:
                        print(f"⚠️ No transcript object found in media data")
                        print(f"📋 Available media attributes: {[attr for attr in dir(media.data) if not attr.startswith('_')]}")
                        if hasattr(media.data, 'transcript'):
                            print(f"📋 Transcript value: {media.data.transcript}")
                        
                        # Try to extract any available text from other media fields
                        alternative_text = None
                        if hasattr(media.data, 'summary') and media.data.summary:
                            alternative_text = f"Meeting Summary: {media.data.summary}"
                            print(f"📝 Found alternative summary text")
                        elif hasattr(media.data, 'title') and media.data.title:
                            alternative_text = f"Meeting Title: {media.data.title}"
                            print(f"📝 Found alternative title text")
                        
                        if alternative_text:
                            transcript_data = [{"speaker": "System", "text": alternative_text}]
                            print(f"💾 Using alternative text as transcript for {notetaker_id}")
                        else:
                            print(f"❌ No alternative text available")
                            # Final fallback: save basic meeting info
                            transcript_data = [{"speaker": "System", "text": f"Meeting recorded but transcript unavailable. Meeting ID: {notetaker_id}"}]
                            print(f"💾 Saving basic meeting info as fallback for {notetaker_id}")

                    if transcript_data is not None:
                        # 2. Update the MongoDB document with the transcript (store as JSON array)
                        await transcript_collection.update_one(
                            {"_id": notetaker_id},
                            {
                                "$set": {
                                    "status": "ready",
                                    "transcript_text": transcript_data,  # Store as JSON array [{'speaker': '...', 'text': '...'}]
                                }
                            },
                        )
                        # Also store in memory for backward compatibility (as combined text)
                        combined_text = "\n\n".join([item.get('text', '') for item in transcript_data if item.get('text')])
                        transcripts[notetaker_id] = combined_text
                        print(f"💾 Transcript ready for {notetaker_id}. Stored {len(transcript_data)} entries in DB.")
                    else:
                        # Handle cases where media is ready but fetching the text failed
                        error_reason = "Media available but failed to fetch transcript text - check logs for details"
                        await transcript_collection.update_one(
                            {"_id": notetaker_id},
                            {"$set": {"status": "failed", "reason": error_reason}},
                        )
                        print(f"❌ Failed to fetch transcript for {notetaker_id} - no transcript data available")
                        print(f"💡 Possible causes:")
                        print(f"   - Transcript URL not accessible")
                        print(f"   - Invalid JSON format in transcript")
                        print(f"   - Empty transcript content")
                        print(f"   - Authentication issues with transcript service")
                    break
            except Exception as e:
                print(f"❌ Error while checking notetaker {notetaker_id}: {e}")
                # Don't fail immediately, continue polling unless it's a critical error
                if retry_count >= max_retries:
                    await transcript_collection.update_one(
                        {"_id": notetaker_id},
                        {"$set": {"status": "failed", "reason": f"Max retries reached. Last error: {e}"}},
                    )
                    break

            # Use asynchronous sleep to avoid blocking
            await asyncio.sleep(30)
        
        # If we exit the loop without finding media
        if retry_count >= max_retries:
            print(f"⏱️ Timeout: Notetaker {notetaker_id} did not become ready after {max_retries} checks")
            await transcript_collection.update_one(
                {"_id": notetaker_id},
                {"$set": {"status": "timeout", "reason": "Notetaker did not complete within expected time"}},
            )