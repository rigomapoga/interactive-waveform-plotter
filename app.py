import math
import numpy as np
import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS # Import CORS

# Initialize Flask app and SocketIO
app = Flask(__name__)

# --- IMPORTANT: Configure Secret Key ---
# In a real production environment, you would never hardcode this.
# For Render, you should set SECRET_KEY as an environment variable in the Render Dashboard.
# os.environ.get() attempts to get the value from environment variables first.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_for_development')
# Replace 'your_super_secret_key_for_development' with a long, random string
# when developing locally or if not using Render's environment variables for SECRET_KEY.

# --- Configure SocketIO for CORS ---
# CORS (Cross-Origin Resource Sharing) is essential when your JavaScript frontend
# (on your WordPress domain) tries to connect to your Python backend (on Render's domain).
# For testing and development, "cors_allowed_origins='*'" allows connections from any origin.
# For production, it is HIGHLY RECOMMENDED to replace '*' with the specific domain(s)
# of your WordPress website(s) for security reasons, e.g.:
# socketio = SocketIO(app, cors_allowed_origins=["https://yourwordpressdomain.com", "https://anotherdomain.com"])
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configure Flask-CORS for regular HTTP routes ---
# While Socket.IO handles its own CORS, if you were to add any other Flask routes
# that serve API data via standard HTTP (not WebSockets), Flask-CORS ensures those
# routes also respect CORS policies. For this app, it's mostly for completeness.
CORS(app)

class WaveformGenerator:
    """
    Generates numerical data for different types of waveforms.
    """
    def __init__(self, sample_rate: int = 1000, duration: float = 1.0):
        self.sample_rate = sample_rate
        self.duration = duration
        # numpy.linspace creates evenly spaced numbers over a specified interval.
        # This forms the 'time' axis for your waveform samples.
        self.time_points = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    def _generate_wave(self, wave_type: str, frequency: float, amplitude: float) -> list[float]:
        """
        Generates waveform data based on type, frequency, and amplitude.
        Args:
            wave_type (str): Type of wave ('sine', 'square', 'sawtooth').
            frequency (float): Frequency of the wave in Hz.
            amplitude (float): Amplitude of the wave (0.0 to 1.0).
        Returns:
            list[float]: A list of numerical sample values for the waveform.
        """
        if wave_type == 'sine':
            samples = amplitude * np.sin(2 * np.pi * frequency * self.time_points)
        elif wave_type == 'square':
            samples = amplitude * np.sign(np.sin(2 * np.pi * frequency * self.time_points))
        elif wave_type == 'sawtooth':
            samples = amplitude * (2 * (np.fmod(self.time_points * frequency, 1.0)) - 1)
        else:
            samples = np.zeros_like(self.time_points) # Default to silent if type is unknown
        
        return samples.tolist() # Convert numpy array to standard Python list for JSON serialization

# --- Flask Routes ---
@app.route('/')
def index():
    """
    Serves the main HTML page.
    Flask looks for templates (HTML files) in a 'templates' directory by default.
    So, ensure your 'index.html' is located at 'your_project_folder/templates/index.html'.
    """
    return render_template('index.html')

# --- Socket.IO Events ---

@socketio.on('connect')
def test_connect():
    """
    Handles new client connections to the WebSocket.
    When a client connects, an initial waveform is generated and sent.
    """
    print('Client connected:', request.sid) # request.sid is the unique session ID for the connected client.
    # Define initial parameters for the waveform.
    initial_params = {'type': 'sine', 'frequency': 2.0, 'amplitude': 0.7}
    generator = WaveformGenerator()
    waveform_data = generator._generate_wave(
        initial_params['type'],
        initial_params['frequency'],
        initial_params['amplitude']
    )
    # emit sends a message over the WebSocket connection.
    # 'waveform_data' is the custom event name that the JavaScript frontend listens for.
    # The dictionary payload is automatically converted to JSON.
    # By default, emit sends to the current client that triggered the event (the one that just connected).
    emit('waveform_data', {'data': waveform_data, 'params': initial_params})

@socketio.on('disconnect')
def test_disconnect():
    """
    Handles client disconnections from the WebSocket.
    """
    print('Client disconnected:', request.sid)

@socketio.on('update_params')
def handle_update_params(params):
    """
    Receives updated waveform parameters from the client (via WebSocket event 'update_params'),
    generates new waveform data, and sends it back to the client.
    Args:
        params (dict): A dictionary containing 'type', 'frequency', and 'amplitude'.
    """
    # .get() is a safe way to access dictionary values, providing a default if the key is missing.
    wave_type = params.get('type', 'sine')
    frequency = float(params.get('frequency', 1.0)) # Convert to float
    amplitude = float(params.get('amplitude', 0.5)) # Convert to float

    # Basic input validation to keep values within reasonable bounds for the plot.
    frequency = max(0.1, min(frequency, 20.0)) # Frequency from 0.1 to 20.0 Hz
    amplitude = max(0.0, min(amplitude, 1.0)) # Amplitude from 0.0 to 1.0

    generator = WaveformGenerator() # Create a new generator instance for each request.
    waveform_data = generator._generate_wave(wave_type, frequency, amplitude)
    
    # Emit the updated data back to the specific client that sent the request.
    # This keeps the communication efficient and targeted.
    emit('waveform_data', {'data': waveform_data, 'params': {'type': wave_type, 'frequency': frequency, 'amplitude': amplitude}})
    print(f"Received params from {request.sid}: {wave_type}, {frequency}Hz, {amplitude}Amp. Sent new data.")


# --- Main Execution Block ---
# This block of code only runs when the script is executed directly (e.g., 'python app.py').
# It will NOT run if this 'app.py' file is imported as a module into another script.
if __name__ == '__main__':
    # Determine the directory where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the full path to the 'templates' directory.
    template_dir = os.path.join(script_dir, 'templates')
    
    # Check if the 'templates' directory exists.
    if not os.path.exists(template_dir):
        os.makedirs(template_dir) # If not, create it.
        print(f"Created templates directory: {template_dir}")

    # Render automatically sets the 'PORT' environment variable for your application.
    # We use os.environ.get('PORT', 5000) to get Render's port or default to 5000 for local development.
    port = int(os.environ.get('PORT', 5000))
    # We listen on '0.0.0.0' to make the server accessible from outside the local machine (Render requires this).
    host = '0.0.0.0' 

    print(f"Starting Flask-SocketIO server on {host}:{port}...")
    print(f"Open your browser to http://localhost:{port} (for local testing)")
    
    # socketio.run() starts the Flask development server integrated with Socket.IO.
    # debug=True: Enables auto-reloading of the server when Python files change (great for local dev).
    #             DISABLE IN PRODUCTION FOR SECURITY.
    # allow_unsafe_werkzeug=True: Often necessary for the Werkzeug development server (used by Flask's debug mode)
    #                             to function correctly with auto-reloading and external access.
    socketio.run(app, debug=False, host=host, port=port, allow_unsafe_werkzeug=True)
