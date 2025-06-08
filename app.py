import math
import numpy as np
import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Initialize Flask app and SocketIO
app = Flask(__name__)

# --- IMPORTANT: Configure Secret Key ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_for_development')

# --- Configure SocketIO for CORS ---
# For production, replace '*' with your specific WordPress domain(s) for security.
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configure Flask-CORS for regular HTTP routes ---
CORS(app)

class WaveformGenerator:
    """
    Generates numerical data for different types of waveforms.
    """
    def __init__(self, sample_rate: int = 1000, duration: float = 1.0):
        self.sample_rate = sample_rate
        self.duration = duration
        self.time_points = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    def _generate_wave(self, wave_type: str, frequency: float, amplitude: float) -> list[float]:
        """
        Generates waveform data based on type, frequency, and amplitude.
        """
        if wave_type == 'sine':
            samples = amplitude * np.sin(2 * np.pi * frequency * self.time_points)
        elif wave_type == 'square':
            samples = amplitude * np.sign(np.sin(2 * np.pi * frequency * self.time_points))
        elif wave_type == 'sawtooth':
            samples = amplitude * (2 * (np.fmod(self.time_points * frequency, 1.0)) - 1)
        else:
            samples = np.zeros_like(self.time_points)
        
        return samples.tolist()

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

# --- Socket.IO Events ---

@socketio.on('connect')
def test_connect():
    """Handle new client connections."""
    print('Client connected:', request.sid)
    initial_params = {'type': 'sine', 'frequency': 2.0, 'amplitude': 0.7}
    generator = WaveformGenerator()
    waveform_data = generator._generate_wave(
        initial_params['type'],
        initial_params['frequency'],
        initial_params['amplitude']
    )
    emit('waveform_data', {'data': waveform_data, 'params': initial_params})

@socketio.on('disconnect')
def test_disconnect():
    """Handle client disconnections."""
    print('Client disconnected:', request.sid)

@socketio.on('update_params')
def handle_update_params(params):
    """
    Receive updated waveform parameters from the client, generate new data,
    and send it back to the client.
    """
    wave_type = params.get('type', 'sine')
    frequency = float(params.get('frequency', 1.0))
    amplitude = float(params.get('amplitude', 0.5))

    frequency = max(0.1, min(frequency, 20.0))
    amplitude = max(0.0, min(amplitude, 1.0))

    generator = WaveformGenerator()
    waveform_data = generator._generate_wave(wave_type, frequency, amplitude)
    
    emit('waveform_data', {'data': waveform_data, 'params': {'type': wave_type, 'frequency': frequency, 'amplitude': amplitude}})
    print(f"Received params from {request.sid}: {wave_type}, {frequency}Hz, {amplitude}Amp. Sent new data.")


if __name__ == '__main__':
    # This block is now primarily for local development.
    # For Render, Gunicorn will run the 'app' object directly,
    # and Socket.IO will integrate with Gunicorn's event loop.
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(script_dir, 'templates')
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
        print(f"Created templates directory: {template_dir}")

    # For local development, you can still run with socketio.run()
    # For production (like Render), Gunicorn will take over.
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"Running locally with Flask development server on {host}:{port}...")
    print("For production deployment, use Gunicorn with the specified start command.")
    socketio.run(app, debug=True, host=host, port=port, allow_unsafe_werkzeug=True) # Keep for local testing
