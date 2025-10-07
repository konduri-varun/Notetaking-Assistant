// API Base URL - Update this to your backend URL
const API_BASE_URL = 'http://localhost:8000';

// Tab switching
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // Find and activate the corresponding button
        document.querySelectorAll('.tab-btn').forEach(btn => {
            if (btn.getAttribute('onclick').includes(tabName)) {
                btn.classList.add('active');
            }
        });
    }

    // Load recordings when recordings tab is shown
    if (tabName === 'recordings') {
        loadAllRecordings();
    }
    
    // Set date to today when calendar tab is shown
    if (tabName === 'calendar') {
        const dateInput = document.getElementById('event-date');
        if (dateInput && !dateInput.value) {
            const today = new Date().toISOString().split('T')[0];
            dateInput.value = today;
        }
    }
}

// Format time from seconds to MM:SS
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Display result
function showResult(elementId, type, content) {
    const resultDiv = document.getElementById(elementId);
    resultDiv.className = `result show ${type}`;
    resultDiv.innerHTML = content;
}

// Hide result
function hideResult(elementId) {
    const resultDiv = document.getElementById(elementId);
    resultDiv.classList.remove('show');
}

// Schedule Meeting Form
document.getElementById('schedule-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const title = document.getElementById('meeting-title').value;
    const meetingLink = document.getElementById('meeting-link').value;
    const startTime = document.getElementById('start-time').value;
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Scheduling...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/schedule-meeting`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                meeting_link: meetingLink,
                start_time: startTime
            })
        });

        const data = await response.json();

        if (response.ok) {
            showResult('schedule-result', 'success', `
                <h3>✅ ${data.message || 'Meeting Scheduled Successfully!'}</h3>
                
                <div class="result-section">
                    <h4>📅 Meeting Details</h4>
                    <div class="result-item">
                        <strong>Title:</strong> ${data.title}
                    </div>
                    <div class="result-item">
                        <strong>Start Time:</strong> ${data.start_time}
                    </div>
                    <div class="result-item">
                        <strong>Meeting Link:</strong> <a href="${data.meeting_link}" target="_blank" style="color: #667eea; text-decoration: none;">${data.meeting_link}</a>
                    </div>
                    ${data.calendar_link ? `
                        <div class="result-item">
                            <strong>View in Google Calendar:</strong> <a href="${data.calendar_link}" target="_blank" style="color: #667eea; text-decoration: none;">Open Calendar Event</a>
                        </div>
                    ` : ''}
                </div>

                <div class="result-section" style="margin-top: 20px;">
                    <h4>🤖 Bot Configuration</h4>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> <code style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-family: monospace;">${data.notetaker_id}</code>
                        <button onclick="navigator.clipboard.writeText('${data.notetaker_id}')" style="margin-left: 10px; padding: 4px 8px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">📋 Copy</button>
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.bot_status || 'Configured'}
                    </div>
                </div>

                <div class="result-section" style="margin-top: 20px; background: #e8f4f8; padding: 15px; border-radius: 8px;">
                    <h4 style="margin-bottom: 10px;">✅ What Happens Next:</h4>
                    ${data.next_steps ? data.next_steps.map(step => `<p style="margin: 5px 0;">• ${step}</p>`).join('') : `
                        <p>• Event has been added to your Google Calendar</p>
                        <p>• Bot will automatically join at the scheduled time</p>
                        <p>• After the meeting, use the Session ID to check the transcript</p>
                    `}
                </div>
            `);
            
            // Clear form
            e.target.reset();
        } else {
            showResult('schedule-result', 'error', `
                <h3>❌ Error</h3>
                <p>${data.detail || 'Failed to schedule meeting'}</p>
            `);
        }
    } catch (error) {
        showResult('schedule-result', 'error', `
            <h3>❌ Connection Error</h3>
            <p>Could not connect to the server. Make sure the backend is running.</p>
        `);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Schedule Meeting';
    }
});

// Check Transcript Form
document.getElementById('check-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const notetakerId = document.getElementById('notetaker-id').value;
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Checking...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/transcripts/${notetakerId}`);
        const data = await response.json();

        if (response.ok) {
            if (data.status === 'ready' && data.transcript_text) {
                // Show only status, no transcript text
                showResult('check-result', 'success', `
                    <h3>📄 ${data.display_status || 'Media Available'}</h3>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> ${data.notetaker_id}
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.display_status || data.status}
                    </div>
                    <p style="margin-top: 15px; background: #d4edda; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745;">
                        ✅ <strong>Transcript is ready!</strong><br>
                        Go to the "All Recordings" tab to view the full transcript.
                    </p>
                `);
            } else if (data.status === 'scheduled') {
                showResult('check-result', 'info', `
                    <h3>📅 Meeting Scheduled</h3>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> ${data.notetaker_id}
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.display_status || data.status}
                    </div>
                    ${data.meeting_title ? `
                        <div class="result-item">
                            <strong>Meeting:</strong> ${data.meeting_title}
                        </div>
                    ` : ''}
                    ${data.scheduled_time ? `
                        <div class="result-item">
                            <strong>Scheduled Time:</strong> ${new Date(data.scheduled_time).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'})}
                        </div>
                    ` : ''}
                    <p style="margin-top: 15px; background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
                        ⏰ <strong>Meeting hasn't started yet.</strong><br>
                        The bot will automatically join at the scheduled time. Check back after the meeting ends to view the transcript.
                    </p>
                `);
            } else if (data.status === 'recording') {
                showResult('check-result', 'info', `
                    <h3>👥 Attending</h3>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> ${data.notetaker_id}
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.display_status || 'Attending'}
                    </div>
                    <p style="margin-top: 15px; background: #d1ecf1; padding: 15px; border-radius: 8px; border-left: 4px solid #0dcaf0;">
                        🎙️ <strong>Meeting in progress!</strong><br>
                        The bot is currently attending the meeting and recording. Check back after the meeting ends to view the transcript.
                    </p>
                `);
            } else if (data.status === 'processing') {
                showResult('check-result', 'info', `
                    <h3>⚙️ Processing</h3>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> ${data.notetaker_id}
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.display_status || 'Processing'}
                    </div>
                    <p style="margin-top: 15px; background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
                        ⏳ <strong>Generating transcript...</strong><br>
                        The meeting has ended and the transcript is being processed. This usually takes a few minutes. Please check again shortly.
                    </p>
                `);
            } else if (data.status === 'failed') {
                showResult('check-result', 'error', `
                    <h3>❌ Failed</h3>
                    <div class="result-item">
                        <strong>Notetaker ID:</strong> ${data.notetaker_id}
                    </div>
                    <div class="result-item">
                        <strong>Status:</strong> ${data.display_status || data.status}
                    </div>
                    <div class="result-item">
                        <strong>Reason:</strong> ${data.reason || 'Unknown error'}
                    </div>
                `);
            }
        } else {
            showResult('check-result', 'error', `
                <h3>❌ Error</h3>
                <p>${data.detail || 'Session not found'}</p>
            `);
        }
    } catch (error) {
        showResult('check-result', 'error', `
            <h3>❌ Connection Error</h3>
            <p>Could not connect to the server. Make sure the backend is running.</p>
        `);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Check Status';
    }
});

// Parse transcript text - extract ONLY text, remove all metadata
function parseTranscriptText(transcriptData) {
    try {
        // If it's a string (already formatted with speakers by backend)
        if (typeof transcriptData === 'string') {
            // If it contains speaker formatting (e.g., "Speaker: text"), return as-is
            if (transcriptData.includes(': ')) {
                return transcriptData.trim();
            }

            // Try to parse as JSON (if backend sends proper JSON)
            try {
                const parsed = JSON.parse(transcriptData);
                if (Array.isArray(parsed)) {
                    // Extract text with speakers from array of objects
                    const textParts = parsed
                        .filter(item => item && typeof item === 'object' && item.text)
                        .map(item => {
                            const speaker = item.speaker || 'Speaker';
                            return `${speaker}: ${item.text.trim()}`;
                        })
                        .filter(text => text.length > 0);
                    return textParts.join('\n\n');
                }
            } catch (jsonError) {
                // Not JSON, might be Python string representation like "[{...}]"
                // Try to extract text with speakers using regex
                const speakerTextMatches = transcriptData.match(/'speaker':\s*'([^']+)',\s*'text':\s*'([^']+)'/g);
                if (speakerTextMatches && speakerTextMatches.length > 0) {
                    const texts = speakerTextMatches.map(match => {
                        const matchResult = match.match(/'speaker':\s*'([^']+)',\s*'text':\s*'([^']+)'/);
                        if (matchResult) {
                            const speaker = matchResult[1];
                            const text = matchResult[2];
                            return `${speaker}: ${text}`;
                        }
                        return '';
                    }).filter(text => text.length > 0);
                    return texts.join('\n\n');
                }

                // Alternative: try to extract using "speaker": "...", "text": "..." pattern (with double quotes)
                const speakerTextMatches2 = transcriptData.match(/"speaker":\s*"([^"]+)",\s*"text":\s*"([^"]+)"/g);
                if (speakerTextMatches2 && speakerTextMatches2.length > 0) {
                    const texts = speakerTextMatches2.map(match => {
                        const matchResult = match.match(/"speaker":\s*"([^"]+)",\s*"text":\s*"([^"]+)"/);
                        if (matchResult) {
                            const speaker = matchResult[1];
                            const text = matchResult[2];
                            return `${speaker}: ${text}`;
                        }
                        return '';
                    }).filter(text => text.length > 0);
                    return texts.join('\n\n');
                }

                // If no patterns matched, return as is (already clean text)
                return transcriptData.trim();
            }
        }

        // If it's already an array
        if (Array.isArray(transcriptData)) {
            const textArray = transcriptData
                .filter(seg => seg && typeof seg === 'object' && seg.text)
                .map(seg => {
                    const speaker = seg.speaker || 'Speaker';
                    return `${speaker}: ${seg.text.trim()}`;
                })
                .filter(text => text.length > 0);
            return textArray.join('\n\n');
        }

        // Last resort: convert to string
        return String(transcriptData).trim();
    } catch (e) {
        console.error('Error parsing transcript:', e);
        return 'Unable to parse transcript';
    }
}

// Load all recordings
async function loadAllRecordings() {
    const container = document.getElementById('recordings-container');
    container.innerHTML = '<div class="loading">Loading recordings...</div>';
    
    try {
        console.log('Fetching recordings from:', `${API_BASE_URL}/recordings`);
        const response = await fetch(`${API_BASE_URL}/recordings`);
        const data = await response.json();
        
        console.log('Recordings response:', data);
        console.log('Total recordings:', data.total);
        console.log('Recordings array:', data.recordings);
        
        if (response.ok && data.recordings && data.recordings.length > 0) {
            container.innerHTML = data.recordings.map(recording => {
                // Use display_status for better UI labels (Attending, Processing, Media Available)
                const displayStatus = recording.display_status || recording.status;
                const statusClass = recording.status.toLowerCase();
                
                // Updated emoji mapping for new statuses
                let statusEmoji = '❓';
                if (displayStatus === 'Media Available' || recording.status === 'ready') {
                    statusEmoji = '📄';
                } else if (displayStatus === 'Attending' || recording.status === 'recording') {
                    statusEmoji = '👥';
                } else if (displayStatus === 'Processing' || recording.status === 'processing') {
                    statusEmoji = '⚙️';
                } else if (recording.status === 'scheduled') {
                    statusEmoji = '📅';
                } else if (recording.status === 'failed') {
                    statusEmoji = '❌';
                }
                
                // Create preview of transcript - SHOW ONLY TEXT (no timestamps, no metadata)
                let previewHtml = '';
                let fullTranscriptHtml = '';
                if (recording.transcript_text && recording.status === 'ready') {
                    const fullText = parseTranscriptText(recording.transcript_text);
                    // Show first 300 characters of pure text
                    const previewText = fullText.substring(0, 300) + (fullText.length > 300 ? '...' : '');
                    previewHtml = `
                        <div class="recording-preview">
                            <div class="transcript-text" style="line-height: 1.6;">
                                📝 ${previewText}
                            </div>
                        </div>
                    `;
                    
                    // Full transcript (hidden by default)
                    fullTranscriptHtml = `
                        <div class="recording-full-transcript" id="transcript-${recording.notetaker_id}" style="display: none; margin-top: 15px; padding: 20px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #667eea;">
                            <h4 style="margin-bottom: 15px; color: #333; text-align: left;">📄 Full Transcript</h4>
                            <div class="transcript-text-full" style="white-space: pre-wrap; line-height: 1.8; max-height: 500px; overflow-y: auto; padding: 15px; background: white; border-radius: 5px; text-align: left; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333;">
                                ${fullText}
                            </div>
                        </div>
                    `;
                }
                
                return `
                    <div class="recording-card ${statusClass}" id="card-${recording.notetaker_id}">
                        <div class="recording-status ${statusClass}">
                            ${statusEmoji} ${displayStatus.toUpperCase()}
                        </div>
                        <div class="recording-notetaker-id">
                            🆔 ${recording.notetaker_id}
                        </div>
                        ${previewHtml}
                        ${fullTranscriptHtml}
                        <div class="recording-actions">
                            <button class="btn-view" id="btn-view-${recording.notetaker_id}" onclick="toggleRecordingView('${recording.notetaker_id}', '${recording.status}')">
                                👁️ View ${recording.status === 'ready' ? 'Full' : 'Details'}
                            </button>
                            <button class="btn-copy" onclick="copyNotetakerId('${recording.notetaker_id}')">
                                📋 Copy ID
                            </button>
                            <button class="btn-delete" onclick="deleteRecording('${recording.notetaker_id}', '${recording.status}')">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = `
                <div class="no-recordings">
                    <h3>📭 No Recordings Yet</h3>
                    <p>Start transcribing meetings to see them here!</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading recordings:', error);
        container.innerHTML = `
            <div class="no-recordings">
                <h3>❌ Error Loading Recordings</h3>
                <p>Could not connect to the server. Make sure backend is running on port 8000.</p>
                <p style="font-size: 0.9em; color: #666; margin-top: 10px;">Error: ${error.message}</p>
            </div>
        `;
    }
}

// Toggle recording view - expand/collapse full transcript inline
function toggleRecordingView(notetakerId, status) {
    const transcriptDiv = document.getElementById(`transcript-${notetakerId}`);
    const button = document.getElementById(`btn-view-${notetakerId}`);
    
    if (transcriptDiv) {
        // Toggle display
        if (transcriptDiv.style.display === 'none') {
            transcriptDiv.style.display = 'block';
            button.innerHTML = '🔼 Hide Full';
            // Smooth scroll to the expanded content
            setTimeout(() => {
                transcriptDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        } else {
            transcriptDiv.style.display = 'none';
            button.innerHTML = '👁️ View Full';
        }
    } else {
        // For non-ready status, fetch and show details in modal
        viewRecordingDetails(notetakerId);
    }
}

// View recording details for non-ready statuses
async function viewRecordingDetails(notetakerId) {
    try {
        const response = await fetch(`${API_BASE_URL}/transcripts/${notetakerId}`);
        const data = await response.json();

        if (response.ok) {
            // Create modal to show details for scheduled/processing/failed recordings
            showTranscriptModal(data);
        } else {
            alert(`Error: ${data.detail || 'Failed to fetch recording'}`);
        }
    } catch (error) {
        alert('Connection Error: Could not connect to the server.');
    }
}

// Copy notetaker ID to clipboard
function copyNotetakerId(notetakerId) {
    navigator.clipboard.writeText(notetakerId);
    
    // Show feedback
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '✅ Copied!';
    button.disabled = true;
    
    setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    }, 2000);
}

// Load recordings when the recordings tab is shown
document.addEventListener('DOMContentLoaded', () => {
    // Load recordings initially
    loadAllRecordings();
});

// Fetch Calendar Events Form
document.getElementById('calendar-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const eventDate = document.getElementById('event-date').value;
    const submitBtn = e.target.querySelector('button[type="submit"]');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Fetching...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/fetch-calendar-events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_date: eventDate
            })
        });

        const data = await response.json();

        if (response.ok) {
            displayCalendarEvents(data);
        } else {
            showResult('calendar-result', 'error', `
                <h3>❌ Error</h3>
                <p>${data.detail || 'Failed to fetch calendar events'}</p>
            `);
            document.getElementById('calendar-events-container').innerHTML = '';
        }
    } catch (error) {
        showResult('calendar-result', 'error', `
            <h3>❌ Connection Error</h3>
            <p>Could not connect to the server. Make sure the backend is running.</p>
        `);
        document.getElementById('calendar-events-container').innerHTML = '';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Fetch Events';
    }
});

// Display calendar events
function displayCalendarEvents(data) {
    const container = document.getElementById('calendar-events-container');
    
    if (data.total_events === 0) {
        showResult('calendar-result', 'info', `
            <h3>📭 No Events Found</h3>
            <p>No calendar events found for the selected date.</p>
        `);
        container.innerHTML = '';
        return;
    }
    
    showResult('calendar-result', 'success', `
        <h3>✅ Found ${data.total_events} Event(s)</h3>
        <div class="result-item">
            <strong>Date Range:</strong> ${data.date_range.start} to ${data.date_range.end}
        </div>
    `);
    
    container.innerHTML = `
        <div class="calendar-events-list">
            ${data.events.map(event => `
                <div class="calendar-event-card">
                    <div class="event-header">
                        <h3 class="event-title">${event.title}</h3>
                        <span class="event-status ${event.status}">${event.status}</span>
                    </div>
                    
                    <div class="event-details">
                        ${event.start_time ? `
                            <div class="event-detail-item">
                                <strong>⏰ Start:</strong> ${event.start_time}
                            </div>
                        ` : ''}
                        
                        ${event.end_time ? `
                            <div class="event-detail-item">
                                <strong>⏱️ End:</strong> ${event.end_time}
                            </div>
                        ` : ''}
                        
                        ${event.conferencing_provider ? `
                            <div class="event-detail-item">
                                <strong>📹 Platform:</strong> ${event.conferencing_provider}
                            </div>
                        ` : ''}
                        
                        ${event.meeting_link ? `
                            <div class="event-detail-item">
                                <strong>🔗 Link:</strong> <a href="${event.meeting_link}" target="_blank" class="meeting-link">${event.meeting_link.substring(0, 50)}...</a>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div class="event-actions">
                        ${event.meeting_link ? `
                            <button class="btn btn-primary" onclick="deployBotToEvent('${event.event_id}', '${event.title}')">
                                🤖 Deploy Bot
                            </button>
                        ` : ''}
                        <button class="btn btn-danger" onclick="deleteCalendarEvent('${event.event_id}', '${event.title.replace(/'/g, "\\'")}')">
                            🗑️ Delete Event
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Deploy bot to calendar event
async function deployBotToEvent(eventId, eventTitle) {
    if (!confirm(`Deploy AI bot to join "${eventTitle}"?`)) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '🔄 Deploying...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/auto-deploy-bot`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_id: eventId
            })
        });

        const data = await response.json();

        if (response.ok) {
            showResult('calendar-result', 'success', `
                <h3>✅ Bot Deployed Successfully!</h3>
                <div class="result-item">
                    <strong>Event:</strong> ${data.event_title}
                </div>
                <div class="result-item">
                    <strong>Notetaker ID:</strong> ${data.notetaker_id}
                </div>
                <div class="result-item">
                    <strong>Meeting Link:</strong> <a href="${data.meeting_link}" target="_blank">${data.meeting_link}</a>
                </div>
                <div class="result-item">
                    <strong>Status:</strong> ${data.status}
                </div>
                <p style="margin-top: 15px;">
                    <strong>Next Step:</strong> The bot will join the meeting automatically. After the meeting ends, use Notetaker ID "${data.notetaker_id}" in the "Check Transcript" tab to view the transcript.
                </p>
            `);
            
            button.innerHTML = '✅ Bot Deployed!';
        } else {
            showResult('calendar-result', 'error', `
                <h3>❌ Failed to Deploy Bot</h3>
                <p>${data.detail || 'Unknown error occurred'}</p>
            `);
            button.innerHTML = originalText;
            button.disabled = false;
        }
    } catch (error) {
        showResult('calendar-result', 'error', `
            <h3>❌ Connection Error</h3>
            <p>Could not connect to the server. Make sure the backend is running.</p>
        `);
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Delete calendar event
async function deleteCalendarEvent(eventId, eventTitle) {
    // Confirm deletion
    if (!confirm(`⚠️ Are you sure you want to delete this calendar event?\n\nEvent: ${eventTitle}\n\nThis will remove the event from your Google Calendar and cancel any bot deployment.\n\nThis action cannot be undone!`)) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '🔄 Deleting...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/calendar-events/${eventId}?calendar_id=primary`, {
            method: 'DELETE'
        });

        // Check if response has content before parsing JSON
        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            const text = await response.text();
            if (text) {
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    throw new Error(`Invalid response from server: ${text}`);
                }
            } else {
                data = { success: false, detail: 'Empty response from server' };
            }
        }

        if (response.ok) {
            showResult('calendar-result', 'success', `
                <h3>✅ Event Deleted Successfully!</h3>
                <div class="result-item">
                    <strong>Event:</strong> ${data.event_title}
                </div>
                <div class="result-item">
                    <strong>Event ID:</strong> ${data.deleted_event_id}
                </div>
                <p style="margin-top: 15px;">
                    The event has been removed from your Google Calendar.
                </p>
            `);
            
            // Remove the card from display after a short delay
            setTimeout(() => {
                const card = button.closest('.calendar-event-card');
                if (card) {
                    card.style.transition = 'all 0.3s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.8)';
                    setTimeout(() => {
                        card.remove();
                        
                        // Check if there are any events left
                        const container = document.getElementById('calendar-events-container');
                        const remainingCards = container.querySelectorAll('.calendar-event-card');
                        if (remainingCards.length === 0) {
                            container.innerHTML = '';
                            showResult('calendar-result', 'info', `
                                <h3>📭 No Events</h3>
                                <p>All events have been deleted or no events exist for this date.</p>
                            `);
                        }
                    }, 300);
                }
            }, 1500);
        } else {
            showResult('calendar-result', 'error', `
                <h3>❌ Failed to Delete Event</h3>
                <p>${data.detail || 'Unknown error occurred'}</p>
            `);
            button.innerHTML = originalText;
            button.disabled = false;
        }
    } catch (error) {
        console.error('Delete event error:', error);
        const errorMessage = error.message || 'Could not connect to the server. Make sure the backend is running.';
        showResult('calendar-result', 'error', `
            <h3>❌ Failed to Delete Event</h3>
            <p>Unexpected error while deleting event: ${errorMessage}</p>
            <div class="result-item">
                <strong>Event:</strong> ${eventTitle}
            </div>
        `);
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Add copy to clipboard functionality for notetaker IDs
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('notetaker-id')) {
        const notetakerId = e.target.textContent;
        navigator.clipboard.writeText(notetakerId);
        
        const originalText = e.target.textContent;
        e.target.textContent = '✅ Copied!';
        setTimeout(() => {
            e.target.textContent = originalText;
        }, 2000);
    }
});

// Delete recording
async function deleteRecording(notetakerId, status) {
    // Confirm deletion
    const statusText = status === 'scheduled' ? 'scheduled meeting' : 
                       status === 'ready' ? 'recording with transcript' : 'recording';
    
    if (!confirm(`⚠️ Are you sure you want to delete this ${statusText}?\n\nNotetaker ID: ${notetakerId}\n\nThis action cannot be undone!`)) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '🔄 Deleting...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/recordings/${notetakerId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            // Show success message
            button.innerHTML = '✅ Deleted!';
            
            // Remove the card from display after a short delay
            setTimeout(() => {
                const card = button.closest('.recording-card');
                if (card) {
                    card.style.transition = 'all 0.3s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.8)';
                    setTimeout(() => {
                        card.remove();
                        
                        // Check if there are any recordings left
                        const container = document.getElementById('recordings-container');
                        const remainingCards = container.querySelectorAll('.recording-card');
                        if (remainingCards.length === 0) {
                            container.innerHTML = `
                                <div class="no-recordings">
                                    <h3>📭 No Recordings</h3>
                                    <p>All recordings have been deleted or start scheduling meetings!</p>
                                </div>
                            `;
                        }
                    }, 300);
                }
            }, 1000);
        } else {
            alert(`❌ Failed to delete recording:\n${data.detail || 'Unknown error'}`);
            button.innerHTML = originalText;
            button.disabled = false;
        }
    } catch (error) {
        alert('❌ Connection Error: Could not connect to the server.');
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

// Show transcript in modal
function showTranscriptModal(data) {
    const modal = document.getElementById('transcript-modal');
    const modalBody = document.getElementById('modal-body');
    const modalTitle = document.getElementById('modal-title');
    
    let content = '';
    
    if (data.status === 'ready' && data.transcript_text) {
        // Parse and show full transcript
        const fullText = parseTranscriptText(data.transcript_text);
        
        modalTitle.innerHTML = '📄 Transcript';
        content = `
            <div class="modal-section">
                <div class="modal-info">
                    <div class="info-item">
                        <strong>Notetaker ID:</strong> 
                        <code>${data.notetaker_id}</code>
                        <button onclick="copyToClipboard('${data.notetaker_id}', this)" class="btn-copy-inline">📋</button>
                    </div>
                    <div class="info-item">
                        <strong>Status:</strong> <span class="status-badge success">${data.display_status || data.status}</span>
                    </div>
                </div>
                
                <div class="transcript-full">
                    <h3>📝 Full Transcript</h3>
                    <div class="transcript-text-full">
                        ${fullText}
                    </div>
                </div>
            </div>
        `;
    } else if (data.status === 'scheduled') {
        modalTitle.innerHTML = '📅 Scheduled';
        content = `
            <div class="modal-section">
                <div class="modal-info">
                    <div class="info-item">
                        <strong>Notetaker ID:</strong> <code>${data.notetaker_id}</code>
                    </div>
                    <div class="info-item">
                        <strong>Status:</strong> <span class="status-badge scheduled">${data.display_status || data.status}</span>
                    </div>
                </div>
                <div class="status-message info">
                    ⏰ <strong>Meeting hasn't started yet.</strong><br>
                    The bot will automatically join at the scheduled time. Check back after the meeting ends to view the transcript.
                </div>
            </div>
        `;
    } else if (data.status === 'recording') {
        modalTitle.innerHTML = '👥 Meeting In Progress';
        content = `
            <div class="modal-section">
                <div class="modal-info">
                    <div class="info-item">
                        <strong>Notetaker ID:</strong> <code>${data.notetaker_id}</code>
                    </div>
                    <div class="info-item">
                        <strong>Status:</strong> <span class="status-badge recording">${data.display_status || 'Attending'}</span>
                    </div>
                </div>
                <div class="status-message info">
                    🎙️ <strong>Meeting in progress!</strong><br>
                    The bot is currently attending the meeting and recording. Check back after the meeting ends to view the transcript.
                </div>
            </div>
        `;
    } else if (data.status === 'processing') {
        modalTitle.innerHTML = '⚙️ Processing Transcript';
        content = `
            <div class="modal-section">
                <div class="modal-info">
                    <div class="info-item">
                        <strong>Notetaker ID:</strong> <code>${data.notetaker_id}</code>
                    </div>
                    <div class="info-item">
                        <strong>Status:</strong> <span class="status-badge processing">${data.display_status || 'Processing'}</span>
                    </div>
                </div>
                <div class="status-message warning">
                    ⏳ <strong>Generating transcript...</strong><br>
                    The meeting has ended and the transcript is being processed. This usually takes a few minutes. Please check again shortly.
                </div>
            </div>
        `;
    } else if (data.status === 'failed') {
        modalTitle.innerHTML = '❌ Failed';
        content = `
            <div class="modal-section">
                <div class="modal-info">
                    <div class="info-item">
                        <strong>Notetaker ID:</strong> <code>${data.notetaker_id}</code>
                    </div>
                    <div class="info-item">
                        <strong>Status:</strong> <span class="status-badge failed">${data.display_status || data.status}</span>
                    </div>
                    ${data.reason ? `
                        <div class="info-item">
                            <strong>Reason:</strong> ${data.reason}
                        </div>
                    ` : ''}
                </div>
                <div class="status-message error">
                    ❌ <strong>Transcription failed.</strong><br>
                    ${data.reason || 'Unknown error occurred.'}
                </div>
            </div>
        `;
    }
    
    modalBody.innerHTML = content;
    modal.style.display = 'block';
}

// Close modal
function closeTranscriptModal() {
    const modal = document.getElementById('transcript-modal');
    modal.style.display = 'none';
}

// Copy to clipboard helper
function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text);
    const originalText = button.innerHTML;
    button.innerHTML = '✅';
    button.disabled = true;
    setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    }, 2000);
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('transcript-modal');
    if (event.target === modal) {
        closeTranscriptModal();
    }
}

// Set today's date as default in calendar form
document.addEventListener('DOMContentLoaded', () => {
    const dateInput = document.getElementById('event-date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }
});
