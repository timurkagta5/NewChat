import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/messenger'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['SECRET_KEY'] = 'your-production-secret-key-here'

# Import Flask app
from app import app as application
