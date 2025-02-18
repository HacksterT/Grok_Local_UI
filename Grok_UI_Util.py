import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv
from time import time
from collections import deque
from datetime import datetime, timedelta
import logging
import traceback
from typing import Optional, Dict, Any
from functools import lru_cache

# Configure logging with different levels for file and console
log_filename = f'grok_ui_{datetime.now().strftime("%Y%m%d")}.log'

# File handler with INFO level for important operations
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Console handler with WARNING level for important issues
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

# Configure root logger
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(file_handler)
logging.getLogger().addHandler(console_handler)

class APIError(Exception):
    """Custom exception for API-related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

def handle_error(error: Exception, user_friendly_message: str) -> str:
    """Handle errors in a consistent way, logging them and returning user-friendly messages."""
    error_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if isinstance(error, APIError):
        logging.error(f"API Error {error_id}: {str(error)} - Status: {error.status_code}, Response: {error.response_text}")
        return f"{user_friendly_message} (Error ID: {error_id})"
    else:
        logging.error(f"Error {error_id}: {str(error)}\n{traceback.format_exc()}")
        return f"{user_friendly_message} (Error ID: {error_id})"

# Setup the page configuration
st.set_page_config(page_title="Grok Query Interface", page_icon="🤖", layout="wide")

st.title("Grok Query Interface")
st.write("Welcome, HacksterC! This is a basic UI to query Grok via API when you exceed the limits here.")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_api_config() -> Dict[str, str]:
    """
    Get API configuration with caching for better performance.
    Cached for 1 hour to balance security and performance.
    
    Returns:
        Dict[str, str]: Dictionary containing API key and URL
    """
    try:
        load_dotenv()
        
        # Get API key with fallback chain
        api_key = os.getenv('GROK_API_KEY') or st.secrets.get('GROK_API_KEY')
        if not api_key:
            raise ValueError("API key not found in environment variables or Streamlit secrets")
        
        # Get API URL with fallback chain
        api_url = os.getenv('GROK_API_URL') or st.secrets.get('GROK_API_URL', "https://api.grok.x.ai/v1/chat/completions")
        
        logging.debug("API configuration loaded from cache or initialized")
        return {"api_key": api_key, "api_url": api_url}
    except Exception as e:
        error_msg = handle_error(e, "Failed to load API configuration")
        st.error(error_msg)
        st.stop()

# Get API configuration
API_CONFIG = get_api_config()
API_KEY = API_CONFIG["api_key"]
API_URL = API_CONFIG["api_url"]

# Constants for input validation
MAX_INPUT_LENGTH = 4000
MIN_INPUT_LENGTH = 1

# Constants for rate limiting
MAX_REQUESTS_PER_MINUTE = 10
MAX_REQUESTS_PER_HOUR = 100

class RateLimiter:
    """
    Rate limiter that manages request limits over different time windows.
    Uses Streamlit's session state for persistence across reruns.
    """
    
    def __init__(self, 
                 minute_limit: int = MAX_REQUESTS_PER_MINUTE,
                 hour_limit: int = MAX_REQUESTS_PER_HOUR):
        """
        Initialize rate limiter with configurable limits.
        
        Args:
            minute_limit: Maximum requests allowed per minute
            hour_limit: Maximum requests allowed per hour
        """
        self.minute_limit = minute_limit
        self.hour_limit = hour_limit
        self._initialize_queues()
    
    def _initialize_queues(self) -> None:
        """Initialize or reset request queues in session state."""
        # Use unique keys for this instance
        self.minute_queue_key = 'rate_limiter_minute_requests'
        self.hour_queue_key = 'rate_limiter_hour_requests'
        
        # Initialize queues if they don't exist
        if self.minute_queue_key not in st.session_state:
            st.session_state[self.minute_queue_key] = deque(maxlen=self.minute_limit)
        if self.hour_queue_key not in st.session_state:
            st.session_state[self.hour_queue_key] = deque(maxlen=self.hour_limit)
    
    @property
    def minute_requests(self) -> deque:
        """Get minute requests queue."""
        return st.session_state[self.minute_queue_key]
    
    @property
    def hour_requests(self) -> deque:
        """Get hour requests queue."""
        return st.session_state[self.hour_queue_key]
    
    def _clean_old_requests(self, queue: deque, window_seconds: int) -> None:
        """
        Remove requests older than the time window.
        
        Args:
            queue: Request queue to clean
            window_seconds: Time window in seconds
        """
        current_time = time()
        while queue and queue[0] < current_time - window_seconds:
            queue.popleft()
    
    def _format_wait_time(self, seconds: float) -> str:
        """
        Format wait time into a user-friendly string.
        
        Args:
            seconds: Wait time in seconds
            
        Returns:
            str: Formatted wait time message
        """
        if seconds < 60:
            return f"{int(seconds)} seconds"
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    
    def can_make_request(self) -> tuple[bool, str]:
        """
        Check if a request can be made based on rate limits.
        
        Returns:
            tuple[bool, str]: (True if request allowed, error message if not)
        """
        current_time = time()
        
        # Clean up old requests
        self._clean_old_requests(self.minute_requests, 60)
        self._clean_old_requests(self.hour_requests, 3600)
        
        # Check minute limit
        if len(self.minute_requests) >= self.minute_limit:
            next_available = self.minute_requests[0] + 60
            wait_time = next_available - current_time
            return False, f"Rate limit exceeded. Please wait {self._format_wait_time(wait_time)}."
        
        # Check hour limit
        if len(self.hour_requests) >= self.hour_limit:
            next_available = self.hour_requests[0] + 3600
            wait_time = next_available - current_time
            return False, f"Hourly limit exceeded. Please wait {self._format_wait_time(wait_time)}."
        
        # Add current request to both queues
        self.minute_requests.append(current_time)
        self.hour_requests.append(current_time)
        return True, ""
    
    def get_usage_stats(self) -> dict:
        """
        Get current usage statistics.
        
        Returns:
            dict: Dictionary containing current usage stats
        """
        self._clean_old_requests(self.minute_requests, 60)
        self._clean_old_requests(self.hour_requests, 3600)
        
        return {
            "requests_this_minute": len(self.minute_requests),
            "requests_this_hour": len(self.hour_requests),
            "minute_limit": self.minute_limit,
            "hour_limit": self.hour_limit
        }
    
    def reset(self) -> None:
        """Reset all rate limiting queues."""
        self._initialize_queues()

class ConversationManager:
    """Manages conversation history with efficient storage and display."""
    
    def __init__(self, max_history: int = 50):
        """
        Initialize conversation manager.
        
        Args:
            max_history: Maximum number of conversations to store
        """
        self.max_history = max_history
        self._initialize_history()
    
    def _initialize_history(self) -> None:
        """Initialize or reset conversation history in session state."""
        if 'conversation_history' not in st.session_state:
            st.session_state.conversation_history = []
    
    def add_conversation(self, user_input: str, response: str) -> None:
        """
        Add a new conversation entry to history.
        
        Args:
            user_input: User's input message
            response: AI's response message
        """
        entry = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'user_input': user_input,
            'response': response
        }
        
        # Add new entry and maintain max size
        history = st.session_state.conversation_history
        history.append(entry)
        
        # Trim history if it exceeds max size
        if len(history) > self.max_history:
            st.session_state.conversation_history = history[-self.max_history:]
    
    def clear_history(self) -> None:
        """Clear all conversation history."""
        st.session_state.conversation_history = []
    
    def get_history(self) -> list:
        """
        Get conversation history in reverse chronological order.
        
        Returns:
            list: List of conversation entries, newest first
        """
        return list(reversed(st.session_state.conversation_history))
    
    def display_history(self, default_expanded: int = 1) -> None:
        """
        Display conversation history in the Streamlit UI.
        
        Args:
            default_expanded: Number of most recent conversations to show expanded
        """
        if not st.session_state.conversation_history:
            st.info("No conversation history yet. Start chatting with Grok!")
            return
        
        st.write("### Conversation History")
        
        # Get reversed history once
        history = self.get_history()
        total_conversations = len(history)
        
        # Display summary stats
        st.write(f"Total conversations: {total_conversations}")
        
        # Create columns for filtering options
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("🔍 Search conversations", key="conversation_search")
        with col2:
            show_all = st.checkbox("Show all", value=False, key="show_all_conversations")
        
        # Filter history based on search term
        if search_term:
            history = [
                entry for entry in history
                if search_term.lower() in entry['user_input'].lower() or
                   search_term.lower() in entry['response'].lower()
            ]
            if not history:
                st.warning(f"No conversations found containing '{search_term}'")
                return
        
        # Determine how many conversations to show
        display_count = len(history) if show_all else min(5, len(history))
        
        # Display conversations
        for idx, entry in enumerate(history[:display_count], 1):
            with st.expander(
                f"Conversation {total_conversations - idx + 1} - {format_timestamp(entry['timestamp'])}", 
                expanded=(idx <= default_expanded)
            ):
                st.write("**You:**")
                st.write(entry['user_input'])
                st.write("**Grok:**")
                st.markdown(entry['response'])
        
        # Show load more button if not showing all
        if not show_all and display_count < len(history):
            st.button("Load More", key="load_more_conversations")

def validate_input(user_input: str) -> tuple[bool, str]:
    """Validate user input against defined constraints."""
    if not user_input or not user_input.strip():
        return False, "Input cannot be empty"
    
    if len(user_input) < MIN_INPUT_LENGTH:
        return False, f"Input must be at least {MIN_INPUT_LENGTH} character long"
    
    if len(user_input) > MAX_INPUT_LENGTH:
        return False, f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters"
    
    return True, ""

def validate_api_response(response_data: Dict[str, Any]) -> str:
    """
    Validate API response format and extract content safely.
    
    Args:
        response_data: JSON response from the API
        
    Returns:
        str: The extracted response content
        
    Raises:
        APIError: If the response format is invalid or missing required fields
    """
    # Check for choices array
    choices = response_data.get('choices', [])
    if not choices:
        raise APIError(
            "Invalid API response: missing or empty 'choices' array",
            response_text=str(response_data)
        )
    
    # Get first choice
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise APIError(
            "Invalid API response: first choice is not an object",
            response_text=str(response_data)
        )
    
    # Get message object
    message = first_choice.get('message', {})
    if not isinstance(message, dict):
        raise APIError(
            "Invalid API response: message is not an object",
            response_text=str(response_data)
        )
    
    # Get content
    content = message.get('content')
    if content is None:
        raise APIError(
            "Invalid API response: missing 'content' in message",
            response_text=str(response_data)
        )
    
    return content

def query_grok(user_input: str, temperature: float = 0.7) -> str:
    """
    Make API call to Grok with comprehensive error handling.
    
    Args:
        user_input: The user's input text
        temperature: Controls randomness in the response (0.0 to 1.0)
    """
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant."
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "model": "grok-2-latest",
            "stream": False,
            "temperature": temperature
        }
        
        # Use debug level for routine operation logging
        logging.debug(f"Making API request to {API_URL} for input length: {len(user_input)}")
        response = requests.post(API_URL, headers=headers, data=json.dumps(data))
        
        # Log response status at different levels based on the status code
        if response.status_code == 200:
            logging.debug(f"API response status code: {response.status_code}")
        else:
            logging.warning(f"API response status code: {response.status_code}")
        
        if response.status_code != 200:
            raise APIError(
                f"API request failed with status {response.status_code}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            raise APIError(
                "Failed to parse API response as JSON",
                response_text=response.text
            ) from e
        
        # Validate and extract content from response
        response_content = validate_api_response(result)
        
        # Log success at debug level
        logging.debug(f"Successfully received response of length: {len(response_content)}")
        return response_content
        
    except requests.RequestException as e:
        error_msg = handle_error(e, "Failed to connect to Grok API")
        return error_msg
    except json.JSONDecodeError as e:
        error_msg = handle_error(e, "Failed to parse API response")
        return error_msg
    except APIError as e:
        error_msg = handle_error(e, "API request failed")
        return error_msg
    except Exception as e:
        error_msg = handle_error(e, "An unexpected error occurred")
        return error_msg

def log_usage_stats(stats: Dict[str, Any]) -> None:
    """Log current usage statistics."""
    logging.info(
        f"Usage Stats - Minute: {stats['requests_this_minute']}/{stats['minute_limit']}, "
        f"Hour: {stats['requests_this_hour']}/{stats['hour_limit']}"
    )

@lru_cache(maxsize=100)
def format_timestamp(timestamp: str) -> str:
    """
    Format timestamp string with caching for repeated timestamps.
    
    Args:
        timestamp: Timestamp string to format
        
    Returns:
        str: Formatted timestamp string
    """
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return timestamp

# Initialize rate limiter and conversation manager
rate_limiter = RateLimiter()
conversation_manager = ConversationManager()

# User input section
user_input = st.text_input("Enter your query:", key="user_input")
submit_button = st.button("Submit Query")

if submit_button and user_input:
    try:
        # Check rate limits
        can_request, limit_message = rate_limiter.can_make_request()
        if not can_request:
            st.error(limit_message)
            logging.warning(f"Rate limit exceeded: {limit_message}")
        else:
            # Process the request
            logging.info(f"Processing request of length: {len(user_input)}")
            response = query_grok(user_input)
            
            # Store in conversation history
            conversation_manager.add_conversation(user_input, response)
            
            # Display the response
            st.write("**Response:**")
            st.write(response)
    except Exception as e:
        error_msg = handle_error(e, "An error occurred while processing your request")
        st.error(error_msg)

# Display conversation history
conversation_manager.display_history()

# Show rate limit information in sidebar
stats = rate_limiter.get_usage_stats()
log_usage_stats(stats)
st.sidebar.write("### API Usage Stats")
st.sidebar.write(f"Requests this minute: {stats['requests_this_minute']}/{stats['minute_limit']}")
st.sidebar.write(f"Requests this hour: {stats['requests_this_hour']}/{stats['hour_limit']}")

# Add clear history button to sidebar
if st.sidebar.button("Clear Conversation History"):
    conversation_manager.clear_history()
    st.experimental_rerun()

# Add some information or disclaimer
st.sidebar.write("### About")
st.sidebar.write("Note: This is a local interface for Grok queries. Please ensure you have the latest API details and your API key is secure.")
st.sidebar.write("Conversation history is stored in your browser session and will be cleared when you refresh the page.")
