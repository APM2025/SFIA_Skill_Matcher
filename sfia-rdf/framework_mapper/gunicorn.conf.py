"""
Gunicorn configuration file for Framework Mapper.
"""
import multiprocessing

# Bind to 0.0.0.0:5001 by default unless overriden by PORT
bind = "0.0.0.0:5001"

# Workers calculation
# Since NLP embedding generation can temporarily block the GIL, we use threads 
# within gunicorn to handle concurrent requests without spinning up completely 
# separate massive PyTorch instances.
workers = 1
threads = 4

# Timeouts
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
