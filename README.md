# Grok UI Utility

A Streamlit-based interface for interacting with the Grok AI API, featuring robust error handling, rate limiting, and conversation management.

## Features

- **API Integration**
  - Configurable API endpoint
  - Secure API key management via .env
  - Comprehensive error handling
  - Rate limiting support

- **User Interface**
  - Clean, intuitive Streamlit interface
  - Simple query input and submission
  - Conversation history display
  - Usage statistics

- **Rate Limiting**
  - Configurable request limits (default: 10/minute, 100/hour)
  - User-friendly wait time messages
  - Session-based tracking

- **Conversation Management**
  - Session-based conversation history
  - Search functionality
  - Pagination support
  - Clear history option

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Copy `.env.template` to `.env` and add your Grok API key
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Use the provided batch file:
```bash
run_grok_ui.bat
```

Note: The batch file uses a specific approach to launch Streamlit that resolves common browser launch issues. It:
1. Changes to the script directory using `cd /d %~dp0`
2. Directly invokes Python from the virtual environment using `venv\Scripts\python.exe -m streamlit`
3. This approach bypasses potential PATH and environment variable issues that can prevent the browser from launching

## Project Structure

```
├── .env.template          # Template for API configuration
├── .streamlit/           # Streamlit configuration
│   └── config.toml      # Streamlit settings
├── Grok_UI_Util.py       # Main application code
├── requirements.txt      # Project dependencies
├── run_grok_ui.bat      # Launch script
└── README.md            # This file
```

## Dependencies

- streamlit>=1.31.0
- requests>=2.31.0
- python-dotenv>=1.0.0

## Next Steps

1. **Persistent Storage**
   - Implement JSON-based conversation storage
   - Add search and filtering capabilities
   - Include backup functionality
   - Add conversation tagging

2. **Enhanced Search**
   - Full-text search implementation
   - Date range filtering
   - Tag-based filtering
   - Search result ranking

3. **UI Improvements**
   - Advanced search interface
   - Export/Import functionality
   - Better conversation visualization
   - Keyboard shortcuts

4. **Performance Optimizations**
   - Implement caching
   - Add compression for large histories
   - Optimize search indexing
   - Improve pagination

## Known Issues

- Conversation history is currently session-based only
- Rate limiting is in-memory and resets on application restart

## Security Notes

- API keys are stored in `.env` file (not version controlled)
- Rate limiting helps prevent API abuse
- Logging implements safe practices for sensitive data

## Contributing

Feel free to submit issues and enhancement requests!

## License

[MIT License](LICENSE)
